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
      alert('Đăng ký thành công')
      window.location.href = '/login'
    } else {
      alert(data.error || 'Đăng ký thất bại')
    }
  } catch {
    alert('Không thể kết nối đến máy chủ')
  }
})
