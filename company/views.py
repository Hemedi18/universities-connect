from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Avg, Sum, Count
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse

from .models import Company, Review, Report, District
from .forms import CompanyForm, ReviewForm, ReportForm
from business.models import Item, Category, Comment

# Create your views here.


@login_required
def register_company(request):
    if hasattr(request.user, "company_profile"):
        return redirect("company:dashboard")

    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            company = form.save(commit=False)
            company.user = request.user
            company.save()
            return redirect("company:dashboard")
    else:
        form = CompanyForm()

    return render(request, "company/register.html", {"form": form})


@login_required
def company_dashboard(request):
    # Check if user has a company profile
    if not hasattr(request.user, "company_profile"):
        return redirect("company:register")

    company = request.user.company_profile

    # Date Filtering
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    items = Item.objects.filter(company=company).order_by("-created_at")

    if start_date_str:
        items = items.filter(created_at__date__gte=start_date_str)
    if end_date_str:
        items = items.filter(created_at__date__lte=end_date_str)

    # Overview Stats
    total_products = items.count()
    total_views = items.aggregate(Sum("views"))["views__sum"] or 0
    total_reviews = company.reviews.count()
    avg_rating = company.reviews.aggregate(Avg("rating"))["rating__avg"] or 0

    # Graph 1: Views per Category
    views_per_category = (
        items.values("category_obj__name")
        .annotate(total_views=Sum("views"))
        .order_by("-total_views")
    )
    cat_labels = [
        x["category_obj__name"] or "Uncategorized" for x in views_per_category
    ]
    cat_data = [x["total_views"] for x in views_per_category]

    # Graph 2: Items Status
    status_counts = items.values("status").annotate(count=Count("id"))
    status_labels = [x["status"].title() for x in status_counts]
    status_data = [x["count"] for x in status_counts]

    # Trending (Top Viewed)
    trending_items = items.order_by("-views")[:5]

    # Recent Reviews
    recent_reviews = company.reviews.all().order_by("-created_at")[:5]

    # Recent Comments on Company Products
    recent_comments = Comment.objects.filter(item__company=company).order_by(
        "-created_at"
    )[:20]

    # Suggestions Logic
    suggestions = []
    for item in items:
        issues = []
        if not item.image:
            issues.append("Missing main image")
        if len(item.description) < 50:
            issues.append("Description is too short")
        if item.views < 10 and (timezone.now() - item.created_at).days > 7:
            issues.append("Low visibility - Consider sharing")
        if item.stock_quantity < 3:
            issues.append("Low stock warning")

        if issues:
            suggestions.append({"item": item, "issues": issues})

    context = {
        "company": company,
        "items": items,
        "total_products": total_products,
        "total_views": total_views,
        "total_reviews": total_reviews,
        "avg_rating": avg_rating,
        "cat_labels": cat_labels,
        "cat_data": cat_data,
        "status_labels": status_labels,
        "status_data": status_data,
        "trending_items": trending_items,
        "recent_reviews": recent_reviews,
        "recent_comments": recent_comments,
        "suggestions": suggestions[:5],
        "start_date": start_date_str,
        "end_date": end_date_str,
    }

    return render(request, "company/dashboard.html", context)


@login_required
def edit_company_profile(request):
    if not hasattr(request.user, "company_profile"):
        return redirect("company:register")

    company = request.user.company_profile

    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            company = form.save()
            phone = (company.whatsapp_number or "").strip()
            if phone:
                Item.objects.filter(company=company).update(contact_phone=phone)
            messages.success(request, "Company profile updated. Contact synced to listings.")
            return redirect("company:dashboard")
    else:
        form = CompanyForm(instance=company)

    return render(request, "company/edit_profile.html", {"form": form})


def view_company_profile(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    items_qs = Item.objects.filter(company=company, status="active").order_by(
        "-created_at"
    )

    query = request.GET.get("q")
    if query:
        items_qs = items_qs.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    # Category Filter
    cat_filter = request.GET.get("category")
    if cat_filter:
        items_qs = items_qs.filter(category_obj__id=cat_filter)

    # Separate Pinned Items (Featured) from Main Grid
    pinned_items = items_qs.filter(is_pinned=True)
    items = items_qs.exclude(is_pinned=True)

    # Get categories for filter chips (only categories that have items)
    company_categories = Category.objects.filter(
        items__company=company, items__status="active"
    ).distinct()

    paginator = Paginator(items, 12)  # Show 12 items per page
    page_number = request.GET.get("page")
    items = paginator.get_page(page_number)

    is_following = False
    if request.user.is_authenticated:
        is_following = request.user in company.followers.all()

    # Review Sorting
    review_sort = request.GET.get("review_sort", "newest")
    reviews = company.reviews.all()

    if review_sort == "oldest":
        reviews = reviews.order_by("created_at")
    elif review_sort == "highest":
        reviews = reviews.order_by("-rating")
    elif review_sort == "lowest":
        reviews = reviews.order_by("rating")
    else:  # newest
        reviews = reviews.order_by("-created_at")

    avg_rating = reviews.aggregate(Avg("rating"))["rating__avg"]
    review_form = ReviewForm()
    report_form = ReportForm()

    # Business Hours Logic
    is_open = False
    now = timezone.localtime().time()
    if company.opening_time and company.closing_time:
        if company.opening_time <= now <= company.closing_time:
            is_open = True

    return render(
        request,
        "company/profile.html",
        {
            "company": company,
            "items": items,
            "pinned_items": pinned_items,
            "is_following": is_following,
            "reviews": reviews,
            "avg_rating": avg_rating,
            "review_form": review_form,
            "report_form": report_form,
            "review_sort": review_sort,
            "company_categories": company_categories,
            "current_category": cat_filter,
            "is_open": is_open,
        },
    )


@login_required
def toggle_follow_company(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if request.user in company.followers.all():
        company.followers.remove(request.user)
    else:
        company.followers.add(request.user)
    return redirect("company:profile", company_id=company_id)


@login_required
def add_review(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if request.method == "POST":
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.company = company
            review.user = request.user
            review.save()
    return redirect("company:profile", company_id=company_id)


@login_required
def edit_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    if review.user != request.user:
        return redirect("company:profile", company_id=review.company.id)

    if request.method == "POST":
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            return redirect("company:profile", company_id=review.company.id)
    else:
        form = ReviewForm(instance=review)

    return render(
        request, "company/edit_review.html", {"form": form, "company": review.company}
    )


@login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    company_id = review.company.id
    if review.user == request.user:
        review.delete()
    return redirect("company:profile", company_id=company_id)


@login_required
def report_company(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.company = company
            report.user = request.user
            report.save()
            return redirect("company:profile", company_id=company_id)
    else:
        form = ReportForm()
    return render(request, "company/report.html", {"form": form, "company": company})


def load_districts(request):
    region_id = request.GET.get("region")
    districts = District.objects.filter(region_id=region_id).order_by("name")
    return JsonResponse(list(districts.values("id", "name")), safe=False)
