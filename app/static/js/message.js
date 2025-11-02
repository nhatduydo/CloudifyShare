
const API_BASE = '/messages';
const token = localStorage.getItem('access_token');

const userList = document.querySelector('#userList');
const chatBox = document.querySelector('#chatBox');
const messageForm = document.querySelector('#messageForm');
const searchInput = document.querySelector('#searchUser');
const messageInput = document.querySelector('#messageInput');
const fileInput = document.querySelector('#fileInput');
const chatHeader = document.querySelector('#chatHeader');

async function loadChatList() {
  userList.innerHTML = `<p class="p-3 text-gray-500">Đang tải...</p>`;
  try {
    console.log("token:", token);
    const res = await fetch(`${API_BASE}/list`, {
      headers: {
        'Authorization': `${token}`,
        'Accept': 'application/json'
      }

    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Không thể tải danh sách');
    renderUserList(data.chats);
  } catch (err) {
    userList.innerHTML = `<p class="p-3 text-red-500">${err.message}</p>`;
  }
}

function renderUserList(users) {
  userList.innerHTML = '';
  if (!users.length) {
    userList.innerHTML = `<p class="p-3 text-gray-400">Chưa có cuộc trò chuyện nào</p>`;
    return;
  }

  users.forEach(u => {
    const item = document.createElement('div');
    item.className = 'flex items-center gap-3 p-3 hover:bg-indigo-50 cursor-pointer';
    item.innerHTML = `
      <img src="${u.avatar_url || '/static/img/default-avatar.png'}" class="w-8 h-8 rounded-full">
      <div>
        <p class="font-medium">${u.full_name || u.username}</p>
        <p class="text-xs text-gray-500">${u.status || ''}</p>
      </div>
    `;
    item.addEventListener('click', () => loadConversation(u));
    userList.appendChild(item);
  });
}

searchInput?.addEventListener('input', async (e) => {
  const q = e.target.value.trim();
  if (!q) return loadChatList();
  console.log('Token:', token);
  const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`, {
    headers: { 'Authorization': `${token}` }
  });
  const data = await res.json();
  if (res.ok) renderUserList(data.users);
});

async function loadConversation(user) {
  chatHeader.innerHTML = `
    <div class="flex items-center gap-3">
      <img src="${user.avatar_url || '/static/img/default-avatar.png'}" class="w-8 h-8 rounded-full">
      <p class="font-semibold">${user.full_name || user.username}</p>
    </div>
  `;
  chatBox.innerHTML = `<p class="text-gray-500 text-center py-4">Đang tải tin nhắn...</p>`;
  chatBox.dataset.receiverId = user.id;

  const res = await fetch(`${API_BASE}/conversation/${user.id}`, {
    headers: { 'Authorization': `${token}` }
  });
  const data = await res.json();
  if (!res.ok) {
    chatBox.innerHTML = `<p class="text-red-500 text-center">${data.error}</p>`;
    return;
  }

  chatBox.innerHTML = '';
  data.messages.forEach(m => renderMessage(m));
  chatBox.scrollTop = chatBox.scrollHeight;
}

function renderMessage(msg, isSender = false) {
  const div = document.createElement('div');
  div.className = `flex ${isSender ? 'justify-end' : 'justify-start'} mb-2`;

  const bubble = document.createElement('div');
  bubble.className = `max-w-xs px-3 py-2 rounded-lg text-sm shadow
    ${isSender ? 'bg-indigo-600 text-white' : 'bg-gray-200 text-gray-800'}`;

  if (msg.message_type === 'image' && msg.file_url) {
    const img = document.createElement('img');
    img.src = msg.file_url;
    img.className = 'max-w-[150px] rounded-lg';
    bubble.appendChild(img);
  } else {
    bubble.textContent = msg.content || '(Không có nội dung)';
  }

  div.appendChild(bubble);
  chatBox.appendChild(div);
}

messageForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const receiverId = chatBox.dataset.receiverId;
  if (!receiverId) return alert('Chưa chọn người nhận!');

  const formData = new FormData();
  formData.append('receiver_id', receiverId);
  formData.append('content', messageInput.value);
  formData.append('message_type', fileInput.files.length ? 'image' : 'text');
  if (fileInput.files.length) formData.append('file', fileInput.files[0]);

  const res = await fetch(`${API_BASE}/send`, {
    method: 'POST',
    headers: { 'Authorization': token },
    body: formData
  });

  const data = await res.json();

  if (res.ok) {
    renderMessage({
      sender_id: parseInt(localStorage.getItem('user_id')),
      content: data.data.content,
      message_type: data.data.message_type,
      file_url: data.data.file_url,
      created_at: data.data.created_at
    }, true);

    messageInput.value = '';
    fileInput.value = '';
    chatBox.scrollTop = chatBox.scrollHeight;
  } else {
    alert(data.error || 'Lỗi gửi tin nhắn');
  }
});


loadChatList();
