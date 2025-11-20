const form = document.getElementById('loginForm');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;

  try {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();

    if (res.ok) {
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('user_id', data.user.id);
      localStorage.setItem('user_name', data.user?.name || username);
      localStorage.setItem('user_email', data.user?.email || '');
      localStorage.setItem('user_avatar', data.user?.avatar_url || '/static/img/avatar-default.svg');

      showToast('Đăng nhập thành công!', 'success');
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 1800);
    } else {
      showToast('Sai thông tin đăng nhập', 'error');
    }
  } catch {
    showToast('Không thể kết nối đến máy chủ', 'error');
  }
});
