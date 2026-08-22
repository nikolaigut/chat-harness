import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { listChats, createChat, getChatEvents, sendMessage, getUsage, getBrowserUrl } from './api.js'

function App() {
  const [chats, setChats] = useState([])
  const [selected, setSelected] = useState(null)
  const [events, setEvents] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [browserUrl, setBrowserUrl] = useState(null)

  useEffect(() => {
    loadChats()
    const id = setInterval(loadChats, 5000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (selected) {
      loadEvents(selected.id)
      loadBrowser()
      const id = setInterval(() => loadEvents(selected.id), 2000)
      return () => clearInterval(id)
    }
  }, [selected])

  async function loadBrowser() {
    if (!selected) return
    try {
      const data = await getBrowserUrl(selected.id)
      setBrowserUrl(data.url)
    } catch (e) {
      console.error(e)
    }
  }

  async function loadChats() {
    try {
      const data = await listChats()
      setChats(data)
    } catch (e) {
      console.error(e)
    }
  }

  async function loadEvents(chatId) {
    try {
      const data = await getChatEvents(chatId)
      setEvents(data)
    } catch (e) {
      console.error(e)
    }
  }

  async function handleNewChat() {
    const name = prompt('Chat name?')
    if (!name) return
    const chat = await createChat(name)
    setChats((prev) => [chat, ...prev])
    setSelected(chat)
  }

  async function handleSend(e) {
    e.preventDefault()
    if (!selected || !input.trim()) return
    setLoading(true)
    try {
      await sendMessage(selected.id, input.trim())
      setInput('')
      await loadEvents(selected.id)
      await loadChats()
    } finally {
      setLoading(false)
    }
  }

  async function handleUsage(agent) {
    if (!selected) return
    const data = await getUsage(selected.id, agent)
    alert(`Agent: ${data.agent}\nRemaining: ${data.remaining ?? 'unknown'}\nTotal: ${data.total ?? 'unknown'}\nModel: ${data.model ?? 'unknown'}`)
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <h2>Chat Harness</h2>
        <button onClick={handleNewChat}>+ New chat</button>
        <ul className="chat-list">
          {chats.map((chat) => (
            <li
              key={chat.id}
              className={selected?.id === chat.id ? 'active' : ''}
              onClick={() => setSelected(chat)}
            >
              <div>{chat.name}</div>
              <div className="status">{chat.status} · {chat.selected_agent || 'auto'}</div>
            </li>
          ))}
        </ul>
      </aside>

      <main className="main">
        {selected ? (
          <>
            <h3>{selected.name}</h3>
            <div className="messages">
              {events.map((ev) => (
                <div key={ev.id} className={`message ${ev.role}`}>
                  <div className="meta">{ev.role}</div>
                  {ev.content && <ReactMarkdown>{ev.content}</ReactMarkdown>}
                  {ev.reasoning && (
                    <details>
                      <summary>reasoning</summary>
                      <pre>{ev.reasoning}</pre>
                    </details>
                  )}
                  {ev.tool_calls && <pre>{JSON.stringify(ev.tool_calls, null, 2)}</pre>}
                </div>
              ))}
            </div>
            <form className="input-row" onSubmit={handleSend}>
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type /usage, a message, or @agent ..."
                disabled={loading}
              />
              <button disabled={loading}>{loading ? '...' : 'Send'}</button>
            </form>
            <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
              <button onClick={() => handleUsage('devin')}>Devin /usage</button>
              <button onClick={() => handleUsage('agy')}>AGY /usage</button>
            </div>
          </>
        ) : (
          <div className="placeholder">Select or create a chat.</div>
        )}
      </main>

      <aside className="browser-panel">
        <h3>Browser</h3>
        {browserUrl ? (
          <iframe title="browser" src={browserUrl} allowFullScreen />
        ) : (
          <div className="placeholder">No browser stream. Start a chat to open a container.</div>
        )}
      </aside>
    </div>
  )
}

export default App
