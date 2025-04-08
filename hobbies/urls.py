from django.urls import path
from .views import ListHobbiesView, SelectHobbiesView, UploadHobbyView
urlpatterns = [
    path('hobbies/', ListHobbiesView.as_view(), name='list-hobbies'),
    path('select-hobbies/', SelectHobbiesView.as_view(), name='select-hobbies'),
    path('upload/', UploadHobbyView.as_view(), name='upload-hobby'),
]