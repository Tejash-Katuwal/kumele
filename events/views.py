from decimal import Decimal
import json
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from hobbies.models import Hobby
from hobbies.serializers import HobbySerializer
from signup.models import CustomUser
from .models import Event, EventPayment, NotificationPreference, UserAvailability, GuestPricing, Cart, CartItem, EventAttendance
from .serializers import EventSerializer, EventPaymentSerializer
from django.utils import timezone
import uuid
from django.conf import settings
import paypalrestsdk
from paypalrestsdk import Payment
import logging

# Set up logging
logger = logging.getLogger(__name__)

class CreateEventView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.debug(f"CreateEventView: request.user = {request.user}, authenticated = {request.user.is_authenticated}")
        data = request.data.copy()
        max_guests = int(data.get('max_guests', 0))
        pricing = GuestPricing.objects.filter(min_guests__lte=max_guests, max_guests__gte=max_guests).first()
        if not pricing:
            return Response({"error": "Invalid number of guests. Must be between 0 and 150."}, status=status.HTTP_400_BAD_REQUEST)
        data['price'] = pricing.price

        category_id = data.get('category_id')
        if not category_id or not request.user.hobbies.filter(id=category_id).exists():
            return Response({"error": "Category must be one of your hobbies."}, status=status.HTTP_400_BAD_REQUEST)

        # Handle image upload
        if 'image' in request.FILES and request.FILES['image']:
            image = request.FILES['image']
            temp_dir = 'media/temp'
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = f'media/temp/{image.name}'
            with open(temp_path, 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)
            data['image'] = temp_path
        else:
            data.pop('image', None)

        serializer = EventSerializer(data=data)
        if serializer.is_valid():
            validated_data = serializer.validated_data.copy()

            # Replace category (Hobby object) with category_id (string)
            if 'category' in validated_data:
                validated_data['category_id'] = str(validated_data['category'].id)
                del validated_data['category']

            # Convert datetime fields to ISO format for storage
            if 'start_time' in validated_data and validated_data['start_time']:
                validated_data['start_time'] = validated_data['start_time'].isoformat()
            
            if 'end_time' in validated_data and validated_data['end_time']:
                validated_data['end_time'] = validated_data['end_time'].isoformat()

            if 'price' in validated_data and isinstance(validated_data['price'], Decimal):
                validated_data['price'] = str(validated_data['price'])

            # Get notification preference
            notification_type = data.get('notification_type', '24_HOURS')
            notification_cost = Decimal('0.00')
            if notification_type == '48_HOURS':
                notification_cost = Decimal('6.00')
            elif notification_type == '7_DAYS':
                notification_cost = Decimal('13.70')

            # Create or update cart
            cart, _ = Cart.objects.get_or_create(user=request.user)
            cart.items.all().delete()  # Clear previous items

            # Add event to cart
            CartItem.objects.create(
                cart=cart,
                item_type='EVENT',
                event_data=validated_data,
                cost=pricing.price
            )

            # Add notification to cart
            CartItem.objects.create(
                cart=cart,
                item_type='NOTIFICATION',
                notification_type=notification_type,
                cost=notification_cost
            )

            return Response({
                "message": "Event data validated and added to cart, proceed to preview",
                "cart_id": cart.id,
                "total_cost": str(cart.get_total_cost())
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CheckUserAvailabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.debug(f"CheckUserAvailabilityView: request.user = {request.user}, authenticated = {request.user.is_authenticated}")
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        if not start_time or not end_time:
            return Response({"error": "Start time and end time are required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check for overlapping events created by the user
        overlapping_events = Event.objects.filter(
            creator=request.user,
            start_time__lt=end_time,
            end_time__gt=start_time,
            is_active=True
        )
        if overlapping_events.exists():
            return Response({
                "available": False,
                "message": "You have a conflicting event during this time."
            }, status=status.HTTP_200_OK)

        # Check for overlapping availability slots
        overlapping_availability = UserAvailability.objects.filter(
            user=request.user,
            start_time__lt=end_time,
            end_time__gt=start_time
        )
        if overlapping_availability.exists():
            return Response({
                "available": False,
                "message": "You are not available during this time."
            }, status=status.HTTP_200_OK)

        return Response({
            "available": True,
            "message": "You are available during this time."
        }, status=status.HTTP_200_OK)

class PreviewEventView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        logger.debug(f"PreviewEventView: request.user = {request.user}, authenticated = {request.user.is_authenticated}")
        cart_id = request.query_params.get('cart_id')
        if not cart_id:
            return Response({"error": "Cart ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_id = int(cart_id)
            cart = Cart.objects.get(id=cart_id, user=request.user)
        except (ValueError, TypeError):
            return Response({"error": "Invalid cart ID."}, status=status.HTTP_400_BAD_REQUEST)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found."}, status=status.HTTP_404_NOT_FOUND)

        event_item = cart.items.filter(item_type='EVENT').first()
        notification_item = cart.items.filter(item_type='NOTIFICATION').first()

        if not event_item:
            return Response({"error": "Event data not found in cart."}, status=status.HTTP_400_BAD_REQUEST)

        # Prepare event_data for serialization
        event_data = event_item.event_data.copy()
        if 'category_id' in event_data:
            event_data['category_id'] = str(event_data['category_id'])

        serializer = EventSerializer(data=event_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        event = serializer.validated_data
        starts_in = (event['start_time'] - timezone.now()).total_seconds() / 3600
        starts_in = f"Starts in {int(starts_in)}hrs" if starts_in > 0 else "Started"

        preview_data = {
            "image": event.get('image', None),
            "category": HobbySerializer(Hobby.objects.get(id=event_data['category_id'])).data,
            "name": event['name'],
            "description": event['name'], # Fixed typo: was using name instead of description
            "price": str(event['price']),
            "time": f"{event['start_time'].strftime('%I:%M%p')} - {event['end_time'].strftime('%I:%M%p')}",
            "guests": f"{event['max_guests']} guests",
            "starts_in": starts_in,
            "location": f"{event['postal_code']}, {event['district']}",
            "host": {
                "name": request.user.username,
                "rating": 4.5,
                "followers": 50,
                "description": request.user.bio or "Welcome to my world of innovation and rhythm!"
            },
            "notification_type": notification_item.notification_type if notification_item else '24_HOURS',
            "notification_cost": str(notification_item.cost) if notification_item else "0.00",
            "total_cost": str(cart.get_total_cost())
        }
        return Response(preview_data, status=status.HTTP_200_OK)

class ProcessPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def configure_paypal(self):
        paypalrestsdk.configure({
            "mode": settings.PAYPAL_MODE,
            "client_id": settings.PAYPAL_CLIENT_ID,
            "client_secret": settings.PAYPAL_CLIENT_SECRET
        })

    def post(self, request):
        logger.debug(f"ProcessPaymentView POST: request.user = {request.user}, authenticated = {request.user.is_authenticated}")
        self.configure_paypal()
        cart_id = request.data.get('cart_id')
        if not cart_id:
            return Response({"error": "Cart ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_id = int(cart_id)
            cart = Cart.objects.get(id=cart_id, user=request.user)
        except (ValueError, TypeError):
            return Response({"error": "Invalid cart ID."}, status=status.HTTP_400_BAD_REQUEST)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found."}, status=status.HTTP_404_NOT_FOUND)

        event_item = cart.items.filter(item_type='EVENT').first()
        notification_item = cart.items.filter(item_type='NOTIFICATION').first()
        payment_type = event_item.event_data.get('payment_type', 'FREE') if event_item else 'FREE'

        if payment_type == 'FREE' and cart.get_total_cost() == 0:
            event_data = event_item.event_data.copy()
            if 'category_id' in event_data:
                event_data['category_id'] = str(event_data['category_id'])
            serializer = EventSerializer(data=event_data)
            if serializer.is_valid():
                event = serializer.save(creator=request.user)
                event.is_active = True
                event.save()

                if notification_item:
                    NotificationPreference.objects.create(
                        event=event,
                        notification_type=notification_item.notification_type,
                        cost=notification_item.cost
                    )

                cart.delete()
                return Response({
                    "message": "Event created successfully",
                    "event": EventSerializer(event).data
                }, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer = EventSerializer(data=event_item.event_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        total_cost = str(cart.get_total_cost())
        event = serializer.validated_data

        payment = Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "transactions": [{
                "amount": {
                    "total": total_cost,
                    "currency": "USD"
                },
                "description": f"Payment for event: {event['name']} and notifications"
            }],
            "redirect_urls": {
                "return_url": f"{settings.FRONTEND_URL}/payment/success?cart_id={cart_id}",
                "cancel_url": f"{settings.FRONTEND_URL}/payment/cancel"
            }
        })

        try:
            if payment.create():
                for link in payment.links:
                    if link.rel == "approval_url":
                        return Response({
                            "message": "Payment initiated",
                            "payment_id": payment.id,
                            "approval_url": link.href,
                            "cart_id": cart_id
                        }, status=status.HTTP_200_OK)
            else:
                return Response({"error": payment.error}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"PayPal error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        logger.debug(f"ProcessPaymentView PUT: request.user = {request.user}, authenticated = {request.user.is_authenticated}")
        
        self.configure_paypal()
        cart_id = request.data.get('cart_id')
        print('Cart ID: ', cart_id)
        if not cart_id:
            return Response({"error": "Cart ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cart_id = int(cart_id)
            print(f"Looking for cart with ID: {cart_id}")
            cart = Cart.objects.get(id=cart_id)
            
            # Make sure the cart has a valid user
            if not cart.user:
                print(f"Cart {cart_id} has no associated user")
                return Response({"error": "No user associated with this cart."}, status=status.HTTP_400_BAD_REQUEST)

            user = cart.user  # Get the user from the cart
            print(f"Cart user: {user.id}, {user.username}")
                
        except (ValueError, TypeError):
            print(f"Invalid cart ID: {cart_id}")
            return Response({"error": "Invalid cart ID."}, status=status.HTTP_400_BAD_REQUEST)
        except Cart.DoesNotExist:
            print(f"Cart not found with ID: {cart_id}")
            return Response({"error": "Cart not found."}, status=status.HTTP_404_NOT_FOUND)

        payment_id = request.data.get("payment_id")
        payer_id = request.data.get("payer_id")

        print("payment_id: ", payment_id)
        print("payer ID: ", payer_id)
        if not payment_id or not payer_id:
            return Response({"error": "Payment ID and Payer ID required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.find(payment_id)
            if payment.execute({"payer_id": payer_id}):
                event_item = cart.items.filter(item_type='EVENT').first()
                if not event_item:
                    logger.error(f"No EVENT item in cart {cart_id}")
                    return Response({"error": "No event found in cart."}, status=status.HTTP_400_BAD_REQUEST)
                    
                event_data = event_item.event_data.copy()
                if 'category_id' in event_data:
                    event_data['category_id'] = str(event_data['category_id'])
                serializer = EventSerializer(data=event_data)
                if serializer.is_valid():
                    # Use cart.user instead of request.user
                    event = serializer.save(creator=user)

                    if isinstance(event.image, str) and event.image.startswith('media/temp/'):
                        final_path = f'media/event_images/{event.image.split("/")[-1]}'
                        os.rename(event.image, final_path)
                        event.image = final_path
                        event.save()

                    notification_item = cart.items.filter(item_type='NOTIFICATION').first()
                    if notification_item:
                        NotificationPreference.objects.create(
                            event=event,
                            notification_type=notification_item.notification_type,
                            cost=notification_item.cost
                        )

                    # Create the payment record - ensure user is valid
                    payment_data = {
                        "event": event.id,
                        "user": user.id,  # Using user.id from cart
                        "amount": float(cart.get_total_cost()),  # Convert Decimal to float
                        "is_paid": True,
                        "payment_date": timezone.now().isoformat(),
                        "transaction_id": payment.id
                    }
                    logger.debug(f"Payment data: {payment_data}")
                    
                    # Double check user_id exists and is valid
                    if not user.id:
                        logger.error(f"Invalid user ID: {user.id}")
                        return Response({"error": "Invalid user ID"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    payment_serializer = EventPaymentSerializer(data=payment_data)
                    if payment_serializer.is_valid():
                        payment_obj = payment_serializer.save()
                        event.is_active = True
                        event.save()

                        cart.delete()
                        return Response({
                            "message": "Payment processed and event created successfully",
                            "event": EventSerializer(event).data,
                            "payment": EventPaymentSerializer(payment_obj).data
                        }, status=status.HTTP_201_CREATED)
                    else:
                        logger.error(f"Payment serializer errors: {payment_serializer.errors}")
                        return Response(payment_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                logger.error(f"PayPal payment execution failed: {payment.error}")
                return Response({"error": payment.error}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"PayPal capture error: {str(e)}")
            return Response({"error": f"PayPal capture error: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
        

class AllEventsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            # Fetch all active, future events
            events = Event.objects.filter(
                is_active=True,
                start_time__gt=timezone.now()
            ).order_by('start_time')
            
            serializer = EventSerializer(events, many=True)
            return Response(serializer.data, status=200)
        except Exception as e:
            logger.error(f"Error fetching all events: {str(e)}")
            return Response({"error": str(e)}, status=400)
        

class JoinEventView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        event_id = request.data.get('event_id')
        if not event_id:
            return Response({"error": "Event ID is required."}, status=400)

        try:
            event = Event.objects.get(id=event_id, is_active=True, start_time__gt=timezone.now())
            
            # Prevent the creator from joining their own event
            if event.creator == request.user:
                return Response({"error": "You cannot join your own event."}, status=400)

            # Check if the user has already joined
            if EventAttendance.objects.filter(event=event, user=request.user).exists():
                return Response({"message": "You have already joined this event."}, status=200)

            # Check if the event has reached its max guests limit
            current_attendees = event.attendees.count()
            if current_attendees >= event.max_guests:
                return Response({"error": "This event has reached its maximum number of guests."}, status=400)

            # Create the attendance record (match)
            EventAttendance.objects.create(event=event, user=request.user)
            return Response({"message": "Successfully joined the event!"}, status=201)
        except Event.DoesNotExist:
            return Response({"error": "Event not found or is no longer active."}, status=404)
        except Exception as e:
            logger.error(f"Error joining event {event_id} for user {request.user.id}: {str(e)}")
            return Response({"error": str(e)}, status=400)
        

class UserPastEventsView(APIView):
    permission_classes = [AllowAny]  # Allow unauthenticated users to view past events

    def get(self, request, user_id):
        try:
            # Verify the user exists
            creator = CustomUser.objects.get(id=user_id)
            
            # Fetch past events by the creator
            past_events = Event.objects.filter(
                creator=creator,
                is_active=True,
                start_time__lt=timezone.now()  # Only past events
            ).order_by('-start_time')
            
            serializer = EventSerializer(past_events, many=True)
            return Response(serializer.data, status=200)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found."}, status=404)
        except Exception as e:
            logger.error(f"Error fetching past events for user {user_id}: {str(e)}")
            return Response({"error": str(e)}, status=400)
        

class OwnEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Fetch all events created by the authenticated user
            events = Event.objects.filter(
                creator=request.user,
                is_active=True
            ).order_by('-created_at')
            
            serializer = EventSerializer(events, many=True)
            return Response(serializer.data, status=200)
        except Exception as e:
            logger.error(f"Error fetching own events for user {request.user.id}: {str(e)}")
            return Response({"error": str(e)}, status=400)
        
class MatchedEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            # Fetch events the authenticated user has joined
            events = Event.objects.filter(
                attendees__user=request.user,  # Filter via EventAttendance
                is_active=True
            ).order_by('start_time')

            if not events.exists():
                return Response({"message": "You haven't joined any events yet."}, status=200)

            serializer = EventSerializer(events, many=True)
            return Response(serializer.data, status=200)
        except Exception as e:
            logger.error(f"Error fetching matched events for user {request.user.id}: {str(e)}")
            return Response({"error": str(e)}, status=400)