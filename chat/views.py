from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
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
