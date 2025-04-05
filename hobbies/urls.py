from django.urls import path
from .views import ListHobbiesView, SelectHobbiesView


urlpatterns = [
    path('hobbies/', ListHobbiesView.as_view(), name='list-hobbies'),
    path('select-hobbies/', SelectHobbiesView.as_view(), name='select-hobbies'),
]