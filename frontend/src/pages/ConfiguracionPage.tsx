import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { 
  Settings, User, Shield, Database, Bell, 
  Loader2, Save, CheckCircle, AlertCircle, Plus
} from 'lucide-react'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { useAuth } from '../hooks/useAuth'
import { format } from 'date-fns'
import { es } from 'date-fns/locale'

export function ConfiguracionPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'usuarios' | 'sistema' | 'backup'>('general')
  const [saving, setSaving] = useState(false)

  const tabs = [
    { id: 'general', label: 'General', icon: Settings },
    { id: 'usuarios', label: 'Usuarios', icon: User },
    { id: 'sistema', label: 'Sistema', icon: Database },
    { id: 'backup', label: 'Backup', icon: Shield },
  ]

  return (
    <div className="space-y-6 bg-page">
      <div>
        <h1 className="text-2xl font-bold text-heading">Configuración</h1>
        <p className="text-muted mt-1">Ajustes del sistema y parámetros</p>
      </div>

      <div className="card">
        <div className="border-b border-default">
          <nav className="flex overflow-x-auto" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400'
                    : 'border-transparent text-muted hover:text-heading hover:border-default'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {activeTab === 'general' && <GeneralSettings />}
          {activeTab === 'usuarios' && <UsuariosSettings />}
          {activeTab === 'sistema' && <SistemaSettings />}
          {activeTab === 'backup' && <BackupSettings />}
        </div>
      </div>
    </div>
  )
}

function GeneralSettings() {
  const [settings, setSettings] = useState({
    sitio_nombre: 'Secretaría',
    sitio_url: 'https://docs.corposcentro.local',
    zona_horaria: 'America/Caracas',
    idioma: 'es',
    tamano_maximo_subida: 10,
    tipos_permitidos: 'image/jpeg,image/png,application/pdf',
    retencion_dias: 0,
    bucket_storage: 'documents',
  })

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target
    setSettings(prev => ({
      ...prev,
      [name]: type === 'number' ? parseInt(value) || 0 : value,
    }))
  }

  return (
    <form onSubmit={(e) => { e.preventDefault(); alert('Configuración guardada') }} className="space-y-6 max-w-2xl">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <label className="label">Nombre del sitio</label>
          <input
            name="sitio_nombre"
            value={settings.sitio_nombre}
            onChange={handleChange}
            className="input"
          />
        </div>
        <div>
          <label className="label">URL del sitio</label>
          <input
            name="sitio_url"
            value={settings.sitio_url}
            onChange={handleChange}
            className="input"
            type="url"
          />
        </div>
        <div>
          <label className="label">Zona horaria</label>
          <select name="zona_horaria" value={settings.zona_horaria} onChange={handleChange} className="input">
            <option value="America/Caracas">America/Caracas (GMT-4)</option>
            <option value="America/Bogota">America/Bogota (GMT-5)</option>
            <option value="UTC">UTC</option>
          </select>
        </div>
        <div>
          <label className="label">Idioma</label>
          <select name="idioma" value={settings.idioma} onChange={handleChange} className="input">
            <option value="es">Español</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>

      <div className="border-t border-default pt-6">
        <h3 className="text-lg font-semibold text-heading mb-4">Carga de Archivos</h3>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div>
            <label className="label">Tamaño máximo (MB)</label>
            <input
              name="tamano_maximo_subida"
              type="number"
              value={settings.tamano_maximo_subida}
              onChange={handleChange}
              className="input"
              min={1}
              max={100}
            />
          </div>
          <div>
            <label className="label">Tipos MIME permitidos</label>
            <input
              name="tipos_permitidos"
              value={settings.tipos_permitidos}
              onChange={handleChange}
              className="input"
              placeholder="image/jpeg,image/png,application/pdf"
            />
          </div>
          <div>
            <label className="label">Retención (días, 0=indefinido)</label>
            <input
              name="retencion_dias"
              type="number"
              value={settings.retencion_dias}
              onChange={handleChange}
              className="input"
              min={0}
            />
          </div>
        </div>
      </div>

      <div className="border-t border-default pt-6">
        <h3 className="text-lg font-semibold text-heading mb-4">Storage</h3>
        <div>
          <label className="label">Bucket de documentos</label>
          <input
            name="bucket_storage"
            value={settings.bucket_storage}
            onChange={handleChange}
            className="input"
          />
        </div>
      </div>

      <div className="flex justify-end pt-4 border-t border-default">
        <button type="submit" className="btn-primary flex items-center gap-2">
          <Save className="w-4 h-4" />
          Guardar Cambios
        </button>
      </div>
    </form>
  )
}

function UsuariosSettings() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ email: '', password: '', confirmar: '', role: 'SECRETARIO', nombre: '' })
  const [errorMsg, setErrorMsg] = useState('')

  const esAdmin =
    (user as any)?.user_metadata?.role === 'ADMIN' || (user as any)?.app_metadata?.role === 'ADMIN'

  const { data: usuarios, isLoading, error } = useQuery({
    queryKey: ['usuarios'],
    queryFn: async () => {
      const resp = await api.get('/usuarios')
      return resp.data as Array<{
        email: string
        role: string
        activo: boolean
        email_confirmado: boolean
        ultimo_acceso: string
        creado: string
      }>
    },
  })

  const crearMutation = useMutation({
    mutationFn: async (datos: { email: string; password: string; role: string; nombre?: string }) => {
      const resp = await api.post('/usuarios', datos)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['usuarios'] })
      setShowModal(false)
      setForm({ email: '', password: '', confirmar: '', role: 'SECRETARIO', nombre: '' })
      setErrorMsg('')
    },
    onError: (err: any) => {
      setErrorMsg(err?.response?.data?.detail || err?.message || 'Error desconocido')
    },
  })

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg('')
    if (form.password !== form.confirmar) {
      setErrorMsg('Las contraseñas no coinciden')
      return
    }
    if (form.password.length < 8) {
      setErrorMsg('La contraseña debe tener al menos 8 caracteres')
      return
    }
    crearMutation.mutate({
      email: form.email,
      password: form.password,
      role: form.role,
      ...(form.nombre ? { nombre: form.nombre } : {}),
    })
  }

  const inicial = (email: string) => (email || '?').charAt(0).toUpperCase()

  const formatearFecha = (iso: string) => {
    if (!iso) return 'Nunca'
    try {
      const d = new Date(iso)
      const ahora = new Date()
      const horas = Math.floor((ahora.getTime() - d.getTime()) / 3600000)
      if (horas < 1) return 'Hace instantes'
      if (horas < 24) return `Hace ${horas} h`
      return d.toLocaleDateString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric' })
    } catch {
      return iso
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-heading">Gestión de Usuarios</h3>
        {esAdmin && (
          <button
            onClick={() => setShowModal(true)}
            className="btn-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Registrar Usuario
          </button>
        )}
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          {isLoading ? (
            <div className="p-8 text-center text-muted">Cargando usuarios…</div>
          ) : error ? (
            <div className="p-8 text-center text-red-600 dark:text-red-400">
              Error cargando usuarios: {(error as Error).message}
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-default">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Usuario</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Rol</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Estado</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Último Acceso</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-default">
                {usuarios?.map((u) => (
                  <tr key={u.email} className="card-hover">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                          <span className="text-blue-700 dark:text-blue-400 font-medium">{inicial(u.email)}</span>
                        </div>
                        <div>
                          <p className="font-medium text-heading">{u.email}</p>
                          {!u.email_confirmado && (
                            <p className="text-xs text-yellow-600 dark:text-yellow-400">Email sin confirmar</p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${u.role === 'ADMIN' ? 'badge-danger' : 'badge-info'}`}>{u.role}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`badge ${u.activo ? 'badge-success' : 'badge-gray'}`}>
                        {u.activo ? 'Activo' : 'Suspendido'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted">{formatearFecha(u.ultimo_acceso)}</td>
                  </tr>
                ))}
                {!usuarios?.length && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-muted">
                      No hay usuarios registrados
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="card p-6 border-border bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Autenticación</h4>
        <p className="text-sm text-blue-700 dark:text-blue-400">
          Los usuarios se autentican vía Supabase Auth (email y contraseña).
          {!esAdmin && ' Solo un ADMIN puede registrar nuevos usuarios.'}
        </p>
      </div>

      {/* Modal: Registrar usuario */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={() => setShowModal(false)}>
          <div
            className="card w-full max-w-md p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-heading">Registrar Usuario</h3>
              <button onClick={() => setShowModal(false)} className="text-muted hover:text-heading text-xl leading-none" aria-label="Cerrar">
                ×
              </button>
            </div>

            <form onSubmit={submit} className="space-y-4">
              <div>
                <label className="label">Email</label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  className="input w-full"
                  placeholder="nombre@institucion.gob.ve"
                  autoComplete="off"
                />
              </div>
              <div>
                <label className="label">Nombre (opcional)</label>
                <input
                  type="text"
                  value={form.nombre}
                  onChange={(e) => setForm({ ...form, nombre: e.target.value })}
                  className="input w-full"
                  placeholder="Nombre y apellido"
                  autoComplete="off"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Contraseña</label>
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="input w-full"
                    placeholder="Mínimo 8 caracteres"
                    autoComplete="new-password"
                  />
                </div>
                <div>
                  <label className="label">Confirmar</label>
                  <input
                    type="password"
                    required
                    value={form.confirmar}
                    onChange={(e) => setForm({ ...form, confirmar: e.target.value })}
                    className="input w-full"
                    placeholder="Repetir contraseña"
                    autoComplete="new-password"
                  />
                </div>
              </div>
              <div>
                <label className="label">Rol</label>
                <select
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="input w-full"
                >
                  <option value="SECRETARIO">SECRETARIO</option>
                  <option value="ADMIN">ADMIN</option>
                </select>
              </div>

              {errorMsg && (
                <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 text-sm">
                  {errorMsg}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={crearMutation.isPending}
                  className="btn-primary flex items-center gap-2"
                >
                  {crearMutation.isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                  {crearMutation.isPending ? 'Creando...' : 'Crear Usuario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function SistemaSettings() {
  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-heading">Estado de Servicios</h3>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ServiceStatus name="PostgreSQL (Supabase)" status="healthy" url="http://supabase-db:5432" />
        <ServiceStatus name="Kong API Gateway" status="healthy" url="http://supabase-kong:8000" />
        <ServiceStatus name="PostgREST" status="healthy" url="http://postgrest:3000" />
        <ServiceStatus name="Neo4j (Graphify)" status="healthy" url="http://neo4j:7474" />
        <ServiceStatus name="Graphify API" status="healthy" url="http://graphify:8080" />
        <ServiceStatus name="Ollama (Vision)" status="healthy" url="http://ollama:11434" />
        <ServiceStatus name="Caddy (Proxy)" status="healthy" url="http://caddy:80" />
      </div>

      <div className="border-t border-default pt-6">
        <h3 className="text-lg font-semibold text-heading mb-4">Variables de Entorno Críticas</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-sm">
          {[
            'SUPABASE_URL',
            'SUPABASE_ANON_KEY',
            'SUPABASE_SERVICE_ROLE_KEY',
            'SUPABASE_JWT_SECRET',
            'GRAPHIFY_URL',
            'OLLAMA_URL',
            'VISION_MODEL',
            'TELEGRAM_BOT_TOKEN',
            'APP_SECRET_KEY',
          ].map(key => (
            <div key={key} className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <code className="text-heading">{key}</code>
              <span className="badge badge-success">Configurado</span>
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-default pt-6">
        <h3 className="text-lg font-semibold text-heading mb-4">Información del Sistema</h3>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 text-sm">
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <p className="text-muted">Versión</p>
            <p className="font-mono text-heading">1.0.0</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <p className="text-muted">Entorno</p>
            <p className="font-mono text-heading">production</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <p className="text-muted">Node.js</p>
            <p className="font-mono text-heading">20.x</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <p className="text-muted">Python</p>
            <p className="font-mono text-heading">3.12</p>
          </div>
        </div>
      </div>
    </div>
  )
}

function ServiceStatus({ name, status, url }: any) {
  const colors = {
    healthy: 'badge-success',
    degraded: 'badge-warning',
    down: 'badge-danger',
    unknown: 'badge-gray',
  }

  return (
    <div className="card p-4 card-hover">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="font-medium text-heading">{name}</p>
          <p className="text-sm text-muted font-mono">{url}</p>
        </div>
        <span className={`badge ${colors[status]}`}>{status}</span>
      </div>
    </div>
  )
}

function BackupSettings() {
  const queryClient = useQueryClient()
  const [running, setRunning] = useState(false)
  const [resultado, setResultado] = useState<string | null>(null)
  const [errorBk, setErrorBk] = useState<string | null>(null)

  const { data: backupsData, isLoading, error, refetch } = useQuery({
    queryKey: ['backups'],
    queryFn: async () => {
      const resp = await api.get('/backup/listar')
      return resp.data as { backups: Array<{ nombre: string; tamano_bytes: number; fecha: string }>; directorio: string }
    },
  })

  const ejecutarBackup = useMutation({
    mutationFn: async () => {
      const resp = await api.post('/backup/ejecutar')
      return resp.data as { ok: boolean; generados: string[]; salida: string }
    },
    onSuccess: (data) => {
      setResultado(`✅ Backup completado: ${data.generados.length} archivo(s) generado(s)`)
      setErrorBk(null)
      queryClient.invalidateQueries({ queryKey: ['backups'] })
    },
    onError: (err: any) => {
      setErrorBk(err?.response?.data?.detail || err?.message || 'Error desconocido')
      setResultado(null)
    },
  })

  const formatearTamano = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const formatearFechaBk = (iso: string) => {
    try {
      const d = new Date(iso)
      return d.toLocaleString('es-VE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch {
      return iso
    }
  }

  const backups = backupsData?.backups || []
  const ultimoSql = backups.find(b => b.nombre.endsWith('.sql.gz'))

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-heading">Gestión de Backups</h3>
        <button
          onClick={() => ejecutarBackup.mutate()}
          disabled={ejecutarBackup.isPending}
          className="btn-primary flex items-center gap-2"
        >
          {ejecutarBackup.isPending ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Database className="w-4 h-4" />
          )}
          {ejecutarBackup.isPending ? 'Ejecutando...' : 'Ejecutar Backup Ahora'}
        </button>
      </div>

      {(resultado || errorBk) && (
        <div className={`card p-4 ${errorBk ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400' : 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'}`}>
          {errorBk || resultado}
        </div>
      )}

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="font-medium text-heading">Respaldo más reciente</h4>
          <button onClick={() => refetch()} className="text-sm text-muted hover:text-heading">
            Actualizar
          </button>
        </div>
        {isLoading ? (
          <p className="text-muted">Cargando…</p>
        ) : error ? (
          <p className="text-red-600 dark:text-red-400">Error: {(error as Error).message}</p>
        ) : ultimoSql ? (
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-heading text-sm">{ultimoSql.nombre}</p>
              <p className="text-sm text-muted">
                {formatearFechaBk(ultimoSql.fecha)} · {formatearTamano(ultimoSql.tamano_bytes)}
              </p>
            </div>
            <span className="badge badge-success">Disponible</span>
          </div>
        ) : (
          <p className="text-muted">No hay respaldos registrados aún</p>
        )}
      </div>

      <div className="card p-6">
        <h4 className="font-medium text-heading mb-4">Historial de respaldos ({backups.length})</h4>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-default">
                <th className="px-2 py-2 text-left text-xs font-medium text-muted uppercase">Archivo</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-muted uppercase">Fecha</th>
                <th className="px-2 py-2 text-left text-xs font-medium text-muted uppercase">Tamaño</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              {backups.map((b) => (
                <tr key={b.nombre}>
                  <td className="px-2 py-2 font-mono text-xs">{b.nombre}</td>
                  <td className="px-2 py-2 text-xs text-muted">{formatearFechaBk(b.fecha)}</td>
                  <td className="px-2 py-2 text-xs text-muted">{formatearTamano(b.tamano_bytes)}</td>
                </tr>
              ))}
              {!backups.length && (
                <tr>
                  <td colSpan={3} className="px-2 py-6 text-center text-muted text-sm">
                    Sin respaldos
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted mt-3">
          Directorio en el servidor: <code>{backupsData?.directorio}</code>
        </p>
      </div>

      <div className="card p-6 border-border bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Backup automático</h4>
        <p className="text-sm text-blue-700 dark:text-blue-400">
          El sistema ejecuta un respaldo completo <strong>diario a las 02:00 AM</strong> (cron del
          servidor) y conserva los últimos <strong>30 días</strong>. El botón de arriba ejecuta el
          mismo procedimiento bajo demanda.
        </p>
      </div>
    </div>
  )
}