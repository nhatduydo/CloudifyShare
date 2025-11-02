const form = document.getElementById('registerForm')
form.addEventListener('submit', async (e) => {
  e.preventDefault()
  const formData = new FormData(form)
  try {
    const res = await fetch('/auth/register', {
      method: 'POST',
      body: formData
    })
    const data = await res.json()
    if (res.ok) {
      showToast('Đăng ký thành công', 'success')
      window.location.href = '/login'
    } else {
      showToast(data.error || 'Đăng ký thất bại', 'error')
    }
  } catch {
    showToast('Không thể kết nối đến máy chủ', 'error')
  }
})
