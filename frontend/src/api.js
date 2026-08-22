const API_BASE = '/api'

export async function listChats() {
  const res = await fetch(`${API_BASE}/chats`)
  return res.json()
}

export async function createChat(name, agent) {
  const res = await fetch(`${API_BASE}/chats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, agent }),
  })
  return res.json()
}

export async function getChatEvents(chatId) {
  const res = await fetch(`${API_BASE}/chats/${chatId}/events`)
  return res.json()
}

export async function sendMessage(chatId, message, agent) {
  const res = await fetch(`${API_BASE}/chats/${chatId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, agent }),
  })
  return res.json()
}

export async function getUsage(chatId, agent) {
  const res = await fetch(`${API_BASE}/chats/${chatId}/usage?agent=${agent || 'devin'}`)
  return res.json()
}

export async function getBrowserUrl(chatId) {
  const res = await fetch(`${API_BASE}/chats/${chatId}/browser`)
  return res.json()
}
