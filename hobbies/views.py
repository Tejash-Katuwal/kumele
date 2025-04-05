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
                "next_step": "welcome"  # After hobbies, direct to welcome screen
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)