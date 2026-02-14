from django.contrib import admin
from .models import Region, District, Company, Review, Report

# Register your models here.
@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'region')
    search_fields = ('name', 'region__name')
    list_filter = ('region',)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_verified', 'created_at')
    list_filter = ('is_verified',)
    search_fields = ('name', 'user__username', 'address')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('company', 'user', 'reason', 'created_at', 'is_resolved')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('company__name', 'user__username', 'reason')
