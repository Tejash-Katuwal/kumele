from django.urls import path
from .views import (CreateEventView, 
    CheckUserAvailabilityView, 
    PreviewEventView, 
    ProcessPaymentView,
    AllEventsView,
    JoinEventView,
    UserPastEventsView,
    OwnEventsView,
    MatchedEventsView)

urlpatterns = [
    path('create-event/', CreateEventView.as_view(), name='create-event'),
    path('check-availability/', CheckUserAvailabilityView.as_view(), name='check-availability'),
    path('preview/', PreviewEventView.as_view(), name='preview-event'),
    path('pay/', ProcessPaymentView.as_view(), name='process-payment'),
    path('events/all/', AllEventsView.as_view(), name='all-events'),
    path('events/join/', JoinEventView.as_view(), name='join-event'),
    path('users/<int:user_id>/past-events/', UserPastEventsView.as_view(), name='user-past-events'),
    path('events/own/', OwnEventsView.as_view(), name='own-events'),
    path('events/matched/', MatchedEventsView.as_view(), name='matched-events'),
]