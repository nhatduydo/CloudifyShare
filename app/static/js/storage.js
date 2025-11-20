const API_BASE = '/files'
const token = localStorage.getItem('access_token')

async function loadFiles() {
  const tableBody = document.getElementById('fileList')
  tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-gray-500 py-4">Đang tải...</td></tr>`
  try {
    const res = await fetch(`${API_BASE}/list`, {
      headers: { 'Authorization': token }
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || 'Không thể tải danh sách')

    if (data.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-gray-400 py-4">Chưa có tệp nào</td></tr>`
      return
    }

    tableBody.innerHTML = ''
    data.forEach(f => {
      const sizeMB = (f.size / 1024 / 1024).toFixed(2)
      const shareStatus = f.is_public
        ? `<span class="text-green-600">Công khai</span>`
        : `<span class="text-gray-500">Riêng tư</span>`

      const actions = `
        <button onclick="toggleShare(${f.id}, ${f.is_public})" class="text-sm text-blue-600 hover:underline">
          ${f.is_public ? 'Tắt chia sẻ' : 'Chia sẻ'}
        </button>
        <button onclick="downloadFile(${f.id})" class="text-sm text-indigo-600 hover:underline">Tải xuống</button>
        <button onclick="deleteFile(${f.id})" class="text-sm text-red-600 hover:underline">Xóa</button>
      `

      const row = document.createElement('tr')
      row.className = 'border-t hover:bg-gray-50'
      row.innerHTML = `
        <td class="py-2 px-3">${f.filename}</td>
        <td class="py-2 px-3 text-center">${sizeMB} MB</td>
        <td class="py-2 px-3 text-center">${f.created_at}</td>
        <td class="py-2 px-3 text-center">${shareStatus}</td>
        <td class="py-2 px-3 text-center space-x-2">${actions}</td>
      `
      tableBody.appendChild(row)
    })
  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="5" class="text-center text-red-500">${err.message}</td></tr>`
  }
}

document.getElementById('fileUpload').addEventListener('change', async (e) => {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  try {
    const res = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      headers: { 'Authorization': token },
      body: formData
    })
    const data = await res.json()
    if (res.ok) {
      showToast('Tải lên thành công!', 'success')
      loadFiles()
    } else {
      showToast('data.error' || 'Lỗi tải lên', 'error')
    }
  } catch {
    showToast('Lỗi kết nối máy chủ!', 'error')
  }
})

async function deleteFile(id) {
  if (!confirm('Bạn có chắc muốn xóa tệp này?')) return
  const res = await fetch(`${API_BASE}/delete/${id}`, {
    method: 'DELETE',
    headers: { 'Authorization': token }
  })
  const data = await res.json()
  showToast('data.message data.error', 'info')
  loadFiles()
}

async function downloadFile(id) {
  const res = await fetch(`${API_BASE}/download/${id}`, {
    headers: { 'Authorization': token }
  })
  const data = await res.json()
  if (res.ok) window.open(data.download_link, '_blank')
}

// async function toggleShare(id, isPublic) {
//   const endpoint = isPublic ? 'make_private' : 'make_public'
//   const res = await fetch(`${API_BASE}/${endpoint}/${id}`, {
//     method: 'PUT',
//     headers: { 'Authorization': token }
//   })
//   const data = await res.json()
//   console.log('Toggle response:', data)
//   showToast(data.message || data.error, 'error')
//   loadFiles()
// }

function addPublicLinkRow(row, url) {
  removePublicLinkRow(row)

  const linkRow = document.createElement('tr')
  linkRow.className = 'public-link-row'
  linkRow.innerHTML = `
    <td colspan="5" class="bg-gray-50 text-sm text-blue-600 py-1 px-3">
      Link công khai: 
      <a href="${url}" target="_blank" class="underline">${url}</a>
      <button class="ml-2 text-xs text-gray-600 underline" onclick="navigator.clipboard.writeText('${url}').then(() => showToast('Đã copy link!', 'success'))">Copy</button>
    </td>
  `
  row.insertAdjacentElement('afterend', linkRow)
}

function removePublicLinkRow(row) {
  const next = row.nextElementSibling
  if (next && next.classList.contains('public-link-row')) {
    next.remove()
  }
}


async function toggleShare(id, isPublic) {
  const endpoint = isPublic ? 'make_private' : 'make_public'
  try {
    const res = await fetch(`${API_BASE}/${endpoint}/${id}`, {
      method: 'PUT',
      headers: { 'Authorization': token }
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || 'Lỗi chia sẻ')

    showToast('data.message', 'info')

    const row = [...document.querySelectorAll('#fileList tr')]
      .find(r => r.innerHTML.includes(`toggleShare(${id}`))

    if (row) {
      const statusCell = row.children[3]
      const actionCell = row.children[4]

      if (endpoint === 'make_public') {
        statusCell.innerHTML = `<span class="text-green-600">Công khai</span>`
        actionCell.children[0].innerText = 'Tắt chia sẻ'
        actionCell.children[0].setAttribute('onclick', `toggleShare(${id}, true)`)

        addPublicLinkRow(row, data.public_url)

      } else {
        statusCell.innerHTML = `<span class="text-gray-500">Riêng tư</span>`
        actionCell.children[0].innerText = 'Chia sẻ'
        actionCell.children[0].setAttribute('onclick', `toggleShare(${id}, false)`)
        removePublicLinkRow(row)
      }
    }

  } catch (err) {
    showToast('err.message', 'error')
  }
}



document.getElementById('searchFile').addEventListener('input', (e) => {
  const keyword = e.target.value.toLowerCase()
  document.querySelectorAll('#fileList tr').forEach(row => {
    const name = row.cells[0]?.textContent.toLowerCase() || ''
    row.style.display = name.includes(keyword) ? '' : 'none'
  })
})

loadFiles()
