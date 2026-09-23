import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { kyc } from '../api'
import Layout from '../components/Layout'

const DOC_TYPES = [
  { value: 'id_card', label: 'Government ID / passport' },
  { value: 'proof_of_address', label: 'Proof of address' },
  { value: 'selfie', label: 'Selfie / photo' },
]

function formatBytes(n) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export default function Kyc() {
  const [docType, setDocType] = useState('id_card')
  const [file, setFile] = useState(null)
  const [docs, setDocs] = useState([])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const fileInput = useRef(null)
  const navigate = useNavigate()

  const load = () => {
    kyc
      .list()
      .then(setDocs)
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    if (!file) {
      setError('Choose a file to upload.')
      return
    }
    setBusy(true)
    try {
      const res = await kyc.uploadDocument(docType, file)
      setMessage(`Uploaded "${res.original_filename}" — status: ${res.status}.`)
      setFile(null)
      if (fileInput.current) fileInput.current.value = ''
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Layout>
      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>Identity</p>
          <h1 className="page-title">Verify your identity</h1>
        </div>
        <Link to="/dashboard" className="btn-outline">← Dashboard</Link>
      </div>

      {error && <div className="error">{error}</div>}
      {message && <div className="notice success">{message}</div>}

      <div className="detail-grid" style={{ marginTop: 4 }}>
        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 18 }}>Upload a document</h3>
          <p className="subtitle">
            Upload a government ID, proof of address, or a selfie so our compliance team can verify
            your account.
          </p>
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="doc_type">Document type</label>
              <select id="doc_type" value={docType} onChange={(e) => setDocType(e.target.value)}>
                {DOC_TYPES.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="file">File</label>
              <input
                id="file"
                type="file"
                ref={fileInput}
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                required
              />
              <p className="hint">Any file type is accepted.</p>
            </div>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? 'Uploading…' : 'Upload document'}
            </button>
          </form>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 18 }}>Your documents</h3>
          {docs.length === 0 && <p className="subtitle">No documents uploaded yet.</p>}
          {docs.map((d) => (
            <div key={d.id} className="kv">
              <span className="k">
                <span style={{ textTransform: 'capitalize' }}>{d.doc_type.replace(/_/g, ' ')}</span>
                <div className="txn-sub">{d.original_filename} · {formatBytes(d.size_bytes)}</div>
              </span>
              <span className="v" style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                <span className={`status-badge ${d.status === 'approved' ? '' : d.status === 'rejected' ? 'failed' : 'pending'}`}>
                  {d.status}
                </span>
                <a href={kyc.downloadUrl(d.id)} target="_blank" rel="noreferrer" className="alt-link" style={{ margin: 0 }}>
                  Download
                </a>
              </span>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  )
}
