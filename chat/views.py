from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.core.cache import cache
from .models import Conversation, Message
from .forms import MessageForm

@login_required
def inbox(request):
    conversations = Conversation.objects.filter(participants=request.user).order_by('-updated_at')
    chats = []
    seen_users = set()

    for conv in conversations:
        other_user = conv.participants.exclude(id=request.user.id).first()
        if other_user:
            if other_user.id in seen_users:
                continue
            seen_users.add(other_user.id)
            
            last_message = conv.messages.last()
            unread_count = conv.messages.filter(is_read=False).exclude(sender=request.user).count()
            chats.append({
                'conversation': conv,
                'other_user': other_user,
                'last_message': last_message,
                'unread_count': unread_count
            })
    return render(request, 'chat/inbox.html', {'chats': chats})

@login_required
def chat_room(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return redirect('chat:inbox')
    
    # Mark messages as read
    unread_messages = conversation.messages.filter(is_read=False).exclude(sender=request.user)
    unread_messages.update(is_read=True)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            conversation.save() # Update updated_at
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message': {
                        'id': message.id,
                        'content': message.content,
                        'timestamp': message.timestamp.strftime("%I:%M %p"),
                        'sender_id': request.user.id
                    }
                })
            return redirect('chat:chat_room', conversation_id=conversation.id)
    else:
        form = MessageForm()
    
    return render(request, 'chat/chat_room.html', {
        'conversation': conversation,
        'messages': conversation.messages.all(),
        'form': form,
        'other_user': conversation.participants.exclude(id=request.user.id).first()
    })

@login_required
def start_chat(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    conversation = Conversation.objects.filter(participants=request.user).filter(participants=target_user).first()
    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, target_user)
    return redirect('chat:chat_room', conversation_id=conversation.id)

@login_required
def get_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Track user online status (expires in 10 seconds)
    cache.set(f'user_online_{request.user.id}', True, 10)
    
    last_id = request.GET.get('last_id')
    messages = conversation.messages.all()
    
    if last_id:
        messages = messages.filter(id__gt=last_id)
    
    # Mark incoming messages as read
    unread = messages.exclude(sender=request.user).filter(is_read=False)
    unread.update(is_read=True)
    
    # Check if other user is online
    other_user = conversation.participants.exclude(id=request.user.id).first()
    other_online = cache.get(f'user_online_{other_user.id}') if other_user else False

    data = []
    for msg in messages:
        # Determine status for new messages
        status = 'sent'
        if msg.is_read:
            status = 'read'
        elif other_online:
            status = 'delivered'

        data.append({
            'id': msg.id,
            'sender_id': msg.sender.id,
            'content': msg.content,
            'timestamp': msg.timestamp.strftime("%I:%M %p"),
            'is_sent': msg.sender == request.user,
            'status': status
        })
    
    # Get status updates for recent sent messages (to update ticks on client)
    status_updates = []
    recent_sent = conversation.messages.filter(sender=request.user).order_by('-id')[:30]
    for msg in recent_sent:
        s = 'sent'
        if msg.is_read: s = 'read'
        elif other_online: s = 'delivered'
        status_updates.append({'id': msg.id, 'status': s})
    
    # Partner info for header
    partner_info = {}
    if other_user:
        partner_info['name'] = other_user.username
        partner_info['is_online'] = other_online
        # Try to get profile image safely
        try:
            if hasattr(other_user, 'profile') and other_user.profile.image:
                partner_info['avatar'] = other_user.profile.image.url
        except Exception:
            pass
            
    return JsonResponse({'messages': data, 'statuses': status_updates, 'partner': partner_info})

@login_required
def update_typing_status(request, conversation_id):
    if request.method == "POST":
        key = f"typing_conversation_{conversation_id}_user_{request.user.id}"
        cache.set(key, True, 3)
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)

@login_required
def check_typing_status(request, conversation_id):
    other_user_id = request.GET.get('other_user_id')
    
    if other_user_id:
        key = f"typing_conversation_{conversation_id}_user_{other_user_id}"
        is_typing = cache.get(key)
        return JsonResponse({"is_typing": bool(is_typing)})
    
    return JsonResponse({"is_typing": False})

@login_required
def get_total_unread(request):
    # Count unread messages in all conversations for this user
    count = Message.objects.filter(conversation__participants=request.user, is_read=False).exclude(sender=request.user).count()
    return JsonResponse({'count': count})
