# hobbies/views.py
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
        # Custom serialization to prioritize icon_url
        hobby_data = []
        for hobby in hobbies:
            hobby_data.append({
                'id': hobby.id,
                'name': hobby.name,
                'icon_url': hobby.icon_url or ''
            })
        return Response(hobby_data, status=status.HTTP_200_OK)
    
class SelectHobbiesView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = SelectHobbiesSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            
            # Custom serialization for hobbies to ensure we use icon_url
            hobbies_data = []
            for hobby in user.hobbies.all():
                hobbies_data.append({
                    'id': hobby.id,
                    'name': hobby.name,
                    'icon_url': hobby.icon_url or ''
                })
                
            return Response({
                "message": "Hobbies updated successfully",
                "hobbies": hobbies_data,
                "next_step": "welcome"  # After hobbies, direct to welcome screen
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)