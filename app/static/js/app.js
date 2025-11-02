function showToast(message, type = 'info', duration = 5000) {
  const container = document.getElementById('toast-container');
  
  const icons = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
    warning: '⚠'
  };
  
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type]}</span>
    <span class="toast-message">${message}</span>
    <button class="toast-close" onclick="this.parentElement.remove()">×</button>
  `;
  
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'slideOut 0.3s var(--ease-standard)';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function showConfirm(message, onConfirm, onCancel) {
  // Nếu đã tồn tại modal thì xóa trước
  const existing = document.querySelector('#confirmModal');
  if (existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'confirmModal';
  modal.className = `fixed inset-0 bg-black/40 flex items-center justify-center z-[9999]`;

  modal.innerHTML = `
    <div class="bg-white rounded-lg shadow-lg w-[350px] p-5 animate-fadeIn">
      <h2 class="text-lg font-semibold text-gray-800 mb-2">Xác nhận</h2>
      <p class="text-gray-600 mb-5">${message}</p>
      <div class="flex justify-end gap-3">
        <button id="cancelBtn" class="px-3 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100">
          Huỷ
        </button>
        <button id="confirmBtn" class="px-3 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700">
          Đồng ý
        </button>
      </div>
    </div>
  `;

  document.body.appendChild(modal);

  return new Promise(resolve => {
    modal.querySelector('#confirmBtn').addEventListener('click', () => {
      modal.remove();
      if (onConfirm) onConfirm();
      resolve(true);
    });

    modal.querySelector('#cancelBtn').addEventListener('click', () => {
      modal.remove();
      if (onCancel) onCancel();
      resolve(false);
    });
  });
}

