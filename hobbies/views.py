from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import Hobby
from .serializers import HobbySerializer, SelectHobbiesSerializer

class ListHobbiesView(APIView):
    permission_classes = [AllowAny]  
    def get(self, request):
        hobbies = Hobby.objects.all()
        serializer = HobbySerializer(hobbies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class SelectHobbiesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = SelectHobbiesSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Hobbies updated successfully",
                "hobbies": HobbySerializer(user.hobbies.all(), many=True).data,
                "next_step": "welcome"
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UploadHobbyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Check if any hobbies were provided
        if not request.data:
            return Response(
                {"error": "At least one hobby name (key) and icon file (value) must be provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # List to store successfully created hobbies
        created_hobbies = []
        # Dictionary to collect errors for each hobby
        errors = {}

        # Iterate over each key-value pair in the request
        for hobby_name, icon_file in request.data.items():
            # Construct data for the serializer
            data = {
                "name": hobby_name,
                "icon": icon_file
            }

            # Validate and save each hobby
            serializer = HobbySerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                created_hobbies.append(serializer.data)
            else:
                # Collect errors for this hobby
                errors[hobby_name] = serializer.errors

        # Prepare the response
        if created_hobbies:
            # If at least one hobby was created successfully
            response_data = {
                "message": "Hobbies processed successfully",
                "created_hobbies": created_hobbies
            }
            if errors:
                # Include errors for any failed hobbies
                response_data["errors"] = errors
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            # If no hobbies were created successfully, return errors
            return Response(
                {"errors": errors},
                status=status.HTTP_400_BAD_REQUEST
            )