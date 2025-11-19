const token = localStorage.getItem('access_token');

async function loadProfile() {
  const res = await fetch('/auth/me', {
    headers: { 'Authorization': token }
  });
  const user = await res.json();

  document.getElementById('avatarPreview').src = user.avatar_url || '/static/img/default-avatar.svg';
  document.getElementById('fullName').value = user.full_name || '';
  document.getElementById('email').value = user.email || '';
}

document.getElementById('btnSaveInfo').addEventListener('click', async () => {
  const full_name = document.getElementById('fullName').value.trim();
  const password = document.getElementById('password').value.trim();

  const res = await fetch('/auth/update-account', {
    method: 'PUT',
    headers: {
      'Authorization': token,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ full_name, password })
  });

  const data = await res.json();
  if (res.ok) {
    showToast('Cập nhật tài khoản thành công!', 'success');
    localStorage.setItem('user_name', full_name);
  } else {
    showToast('data.error', 'error');
  }
});

document.getElementById('btnUpdateAvatar').addEventListener('click', async () => {
  const file = document.getElementById('avatarInput').files[0];
  if (!file) return showToast('Vui lòng chọn ảnh!', 'warning');

  const formData = new FormData();
  formData.append('avatar', file);

  const res = await fetch('/auth/update-avatar', {
    method: 'PUT',
    headers: { 'Authorization': token },
    body: formData
  });

  const data = await res.json();
  if (res.ok) {
    showToast('Ảnh đại diện đã cập nhật!', 'success');
    document.getElementById('avatarPreview').src = data.avatar_url;
    localStorage.setItem('user_avatar', data.avatar_url);
  } else {
    //showToast(data.error, 'error');
  }
});

loadProfile();
