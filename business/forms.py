from django import forms
from .models import Item, ProductAttributeValue, Company, Review, Report, Comment

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'title',
            'sku',
            'category_obj',
            'condition',
            'price',
            'compare_at_price',
            'stock_quantity',
            'description',
            'campus_location',
            'shipping_weight',
            'shipping_dimensions',
            'contact_method',
            'contact_email',
            'contact_phone',
            'image',
            'image2',
            'image3',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'compare_at_price': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'campus_location': forms.TextInput(attrs={'placeholder': 'e.g. Hall 5, Library, Main Gate', 'class': 'form-control'}),
            'shipping_weight': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'shipping_dimensions': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_method': forms.Select(attrs={'class': 'form-select'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'image2': forms.FileInput(attrs={'class': 'form-control'}),
            'image3': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.category = kwargs.pop('category', None)
        super().__init__(*args, **kwargs)

        if self.category:
            # Hide the category field as it's already selected
            self.fields['category_obj'].initial = self.category
            self.fields['category_obj'].widget = forms.HiddenInput()
            self.fields['category_obj'].required = False
            
            # Dynamically add fields for attributes linked to this category
            for attr in self.category.attributes.all():
                field_name = f"attr_{attr.id}"
                
                if attr.options:
                    # Use ChoiceField for fixed options (Dropdown)
                    options = [opt.strip() for opt in attr.options.split(',')]
                    choices = [('', f'Select {attr.name}')] + [(opt, opt) for opt in options]
                    self.fields[field_name] = forms.ChoiceField(
                        label=attr.name,
                        choices=choices,
                        required=False,
                        widget=forms.Select(attrs={'class': 'form-select'})
                    )
                elif attr.name.lower() in ['os', 'operating system', 'platform']:
                    # Fallback for OS if options are not set in DB
                    os_choices = [('', f'Select {attr.name}'), ('Android', 'Android'), ('iOS', 'iOS'), ('Windows', 'Windows'), ('macOS', 'macOS'), ('Linux', 'Linux'), ('Other', 'Other')]
                    self.fields[field_name] = forms.ChoiceField(
                        label=attr.name,
                        choices=os_choices,
                        required=False,
                        widget=forms.Select(attrs={'class': 'form-select'})
                    )

                else:
                    # Heuristics for user-friendly widgets based on attribute name
                    attr_lower = attr.name.lower()
                    widget = forms.TextInput(attrs={'class': 'form-control'})
                    
                    if 'date' in attr_lower or 'year' in attr_lower:
                        widget = forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
                    elif 'color' in attr_lower or 'colour' in attr_lower:
                        widget = forms.TextInput(attrs={'class': 'form-control', 'type': 'color', 'style': 'height: 38px; padding: 4px;'})
                    
                    self.fields[field_name] = forms.CharField(label=attr.name, required=False, widget=widget)
                
                # Add a special class to identify dynamic attributes for JS wizard
                self.fields[field_name].widget.attrs['data-wizard-step'] = '2' # Default to step 2
                # If it's Brand/Make, move to step 1
                if attr.name in ['Brand', 'Make', 'Provider', 'Publisher', 'Company']:
                    self.fields[field_name].widget.attrs['data-wizard-step'] = '1'

    def save(self, commit=True):
        if self.category:
            self.instance.category_obj = self.category
        item = super().save(commit=False)
        if commit:
            item.save()
            # Save dynamic attributes
            for name, value in self.cleaned_data.items():
                if name.startswith('attr_') and value:
                    attr_id = int(name.replace('attr_', ''))
                    ProductAttributeValue.objects.create(product=item, attribute_id=attr_id, value=value)
        return item

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'logo', 'description', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Mlimani City, Dar es Salaam'}),
        }

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.HiddenInput(),
            'comment': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Share your experience...'}),
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ask a question or leave a comment...'})
        }

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'details']
        widgets = {
            'reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason (e.g. Scam, Inappropriate Content)'}),
            'details': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Please provide more details...'}),
        }