from django import forms
from .models import Order, OrderItem

class CancelOrderForm(forms.Form):
    reason = forms.CharField(required=True, widget=forms.Textarea(attrs={
        'rows': 3, 
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        'placeholder': 'Please tell us why you want to cancel (optional)'
    }),
    label='Cancellation Reason (Required)'
    )

    def clean(self):
        cleaned_data = super().clean()
        reason = cleaned_data.get('reason', '').strip()
        if not reason:
            raise forms.ValidationError('Cancel reason is required.')
        if len(reason) < 10:
            raise forms.ValidationError('Please provide a more detailed reason (at least 10 character).')
        cleaned_data['reason'] = reason
        return cleaned_data


class CancelOrderItemForm(forms.Form):
    """Form for cancelling individual order item"""
    reason = forms.CharField(required=True, widget=forms.Textarea(attrs={
        'rows': 3,
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        'placeholder': 'Please explain why you want to return this item (required)'
    }),
    label='Cancellation Reason (Required)'
    )
    def clean_reason(self):
        reason = self.cleaned_data.get('reason', '').strip()
        if not reason:
            raise forms.ValidationError('Cancel reason is required.')
        if len(reason) < 10:
            raise forms.ValidationError('Please provide a more detailed reason (at least 10 character).')
        return reason

class ReturnOrderItemForm(forms.Form):
    """Form for returning order item"""
    reason = forms.CharField(required=True, widget=forms.Textarea(attrs={
        'rows': 4,
        'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        'placeholder': 'Please explain why you want to return this item (required)'
    }),
    label='Return Reason (Required)'
    )

    def clean_reason(self):
        reason = self.cleaned_data.get('reason', '').strip()
        if not reason:
            raise forms.ValidationError('Return reason is required.')
        if len(reason) < 10:
            raise forms.ValidationError('Please provide a more detailed reason (at least 10 character).')
        return reason
    
class AdminOrderStatusForm(forms.ModelForm):
    """Admin form for updating order status"""

    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 2,
        'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
        'placeholder': 'Add notes about this status change (optional)'
    }),
    label='Status Change Notes'
    )

    class Meta:
        model = Order
        fields = ['status', 'tracking_number']
        widgets = {
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'tracking_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter tracking number'
            })
        }

class OrderSearchForm(forms.Form):
    """Form for search orders"""
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'w-full h-25 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
        'placeholder': 'Search by Order ID, Customer Name, Email...'

        }),
        label=''
    )

    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Status')] + Order.STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    payment_method = forms.ChoiceField(
        required=False,
        choices=[('', 'All Payment Methods')] + Order.PAYMENT_METHOD_CHOICES,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        }),
        label='From Date'
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        }),
        label='To Date'
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('-total_amount', 'Highest Amount'),
            ('total_amount', 'Lowest Amount'),
        ],
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
        }),
        initial='-created_at'
    )
