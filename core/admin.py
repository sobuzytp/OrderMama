from django.contrib import admin
from .models import *
for m in [Restaurant,RestaurantMembership,DiningTable,Category,MenuItem,Order,OrderItem,ServiceRequest,Plan,Subscription]: admin.site.register(m)
