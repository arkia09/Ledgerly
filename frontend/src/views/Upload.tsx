import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, CheckCircle2, FileImage, LoaderCircle, Upload as UploadIcon } from 'lucide-react'
import { PageHeader } from '../components/ui'

type Props = { busy: boolean; onRead: (file: File) => void }

export default function Upload({ busy, onRead }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [drag, setDrag] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const pick = (f?: File | null) => { if (f && f.type.startsWith('image/')) setFile(f) }

  return (
    <>
      <PageHeader title="Add a khata page" subtitle="Take a clear photo of one ledger page. You will check every entry before anything is saved." />
      <section className="panel upload">
        <div className={`dropzone ${drag ? 'drag' : ''}`}
          onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
          onDrop={e => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }}>
          <input ref={input} type="file" accept="image/*" hidden onChange={e => pick(e.target.files?.[0])} />
          {file && preview ? (
            <>
              <img src={preview} alt="Selected ledger page" className="upload-preview" />
              <p><FileImage size={20} /> {file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</p>
              <button className="link" onClick={() => input.current?.click()} disabled={busy}>Choose a different photo</button>
            </>
          ) : (
            <>
              <UploadIcon size={44} />
              <h2>Drop a photo here</h2>
              <p>JPG, PNG or WEBP</p>
              <button className="btn" onClick={() => input.current?.click()}>Choose photo</button>
            </>
          )}
        </div>
        <ul className="tips">
          <li><CheckCircle2 size={20} /> Keep the whole page in the frame</li>
          <li><CheckCircle2 size={20} /> Even light, no shadows across the writing</li>
          <li><CheckCircle2 size={20} /> Hold the phone straight above the page</li>
        </ul>
        <button className="btn primary big" disabled={!file || busy} onClick={() => file && onRead(file)}>
          {busy ? <><LoaderCircle className="spin" size={22} /> Reading your page…</> : <>Read this page <ArrowRight size={22} /></>}
        </button>
        {busy && <p className="muted center">The model runs on this computer and can take a few minutes. Keep this tab open.</p>}
      </section>
    </>
  )
}
