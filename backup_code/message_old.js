const API_BASE = '/messages';
const token = localStorage.getItem('access_token');
const myId = parseInt(localStorage.getItem('user_id'));

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
    const res = await fetch(`${API_BASE}/list`, {
      headers: { 'Authorization': token, 'Accept': 'application/json' }
    });
    const data = await res.json();
    if (!res.ok) throw new Error('Không thể tải danh sách');
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
  const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(q)}`, {
    headers: { 'Authorization': token }
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
    headers: { 'Authorization': token }
  });

  const data = await res.json();

  if (!res.ok) {
    //chatBox.innerHTML = `<p class="text-red-500 text-center">${data.error}</p>`;
    return;
  }

  chatBox.innerHTML = '';

  //FIX QUAN TRỌNG: phân loại trái/phải dựa trên sender_id
  data.messages.forEach(msg => {
    console.log(typeof msg.sender_id, msg.sender_id);
    console.log(typeof myId, myId);
    const isSender = Number(msg.sender_id) === Number(myId);
    renderMessage(msg, isSender);
  });

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
    bubble.textContent = msg.content || 'Nội dung này không còn tồn tại';
  }

  div.appendChild(bubble);
  chatBox.appendChild(div);
}

messageForm?.addEventListener('submit', async (e) => {
  e.preventDefault();

  const receiverId = chatBox.dataset.receiverId;
  if (!receiverId) return showToast('Chưa chọn người nhận!', 'error');

  const formData = new FormData();
  formData.append('receiver_id', receiverId);
  formData.append('content', messageInput.value);
  formData.append('message_type', fileInput.files.length ? 'image' : 'text');
  if (fileInput.files.length) formData.append('file', fileInput.files[0]);

  const tempMsg = {
    sender_id: myId,
    content: messageInput.value,
    message_type: fileInput.files.length ? 'image' : 'text',
    file_url: fileInput.files.length ? URL.createObjectURL(fileInput.files[0]) : null
  };
  renderMessage(tempMsg, true);
  chatBox.scrollTop = chatBox.scrollHeight;

  const res = await fetch(`${API_BASE}/send`, {
    method: 'POST',
    headers: { 'Authorization': token },
    body: formData
  });

  const data = await res.json();
  if (!res.ok) {
    return;
  }

  messageInput.value = '';
  fileInput.value = '';
});

const fileNameDisplay = document.querySelector('#fileName');

fileInput.addEventListener('change', () => {
  if (fileInput.files.length > 0) {
    fileNameDisplay.textContent = fileInput.files[0].name;
  } else {
    fileNameDisplay.textContent = '';
  }
});
const removeFileBtn = document.querySelector('#removeFile');

fileInput.addEventListener('change', () => {
  if (fileInput.files.length > 0) {
    fileNameDisplay.textContent = fileInput.files[0].name;
    removeFileBtn.classList.remove('hidden');
  }
});

removeFileBtn.addEventListener('click', () => {
  fileInput.value = '';
  fileNameDisplay.textContent = '';
  removeFileBtn.classList.add('hidden');
});


loadChatList();
