import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { 
  Settings, User, Shield, Database, Bell, 
  Loader2, Save, CheckCircle, AlertCircle, Plus
} from 'lucide-react'
import { LoadingSpinner } from '../components/LoadingSpinner'
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
  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-heading">Gestión de Usuarios</h3>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Invitar Usuario
        </button>
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-default">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Usuario</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Rol</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Estado</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Último Acceso</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              <tr>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                      <span className="text-blue-700 dark:text-blue-400 font-medium">A</span>
                    </div>
                    <div>
                      <p className="font-medium text-heading">Admin Sistema</p>
                      <p className="text-sm text-muted">admin@ejemplo.gob.ve</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className="badge badge-danger">ADMIN</span>
                </td>
                <td className="px-4 py-3">
                  <span className="badge badge-success">Activo</span>
                </td>
                <td className="px-4 py-3 text-sm text-muted">Hace 2 horas</td>
                <td className="px-4 py-3">
                  <button className="text-muted hover:text-heading">Editar</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="card p-6 border-border bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <h4 className="font-medium text-blue-900 dark:text-blue-300 mb-2">Autenticación</h4>
        <p className="text-sm text-blue-700 dark:text-blue-400">
          Los usuarios se autentican vía Supabase Auth (email + magic link).
          Los roles se gestionan desde la tabla <code>personas</code> con <code>telegram_user_id</code>.
        </p>
      </div>
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
  const [lastBackup, setLastBackup] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const handleBackup = async () => {
    setRunning(true)
    // Simular backup
    await new Promise(r => setTimeout(r, 2000))
    setLastBackup(new Date().toISOString())
    setRunning(false)
    alert('Backup completado exitosamente')
  }

  const handleRestore = () => {
    alert('Función de restauración - Seleccionar archivo de backup')
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-heading">Gestión de Backups</h3>
        <button
          onClick={handleBackup}
          disabled={running}
          className="btn-primary flex items-center gap-2"
        >
          {running ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Database className="w-4 h-4" />
          )}
          {running ? 'Ejecutando...' : 'Ejecutar Backup Ahora'}
        </button>
      </div>

      <div className="card p-6">
        <h4 className="font-medium text-heading mb-4">Último Backup</h4>
        {lastBackup ? (
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-heading">{format(new Date(lastBackup), 'dd/MM/yyyy HH:mm:ss', { locale: es })}</p>
              <p className="text-sm text-muted">Backup completo (BD + volúmenes + config)</p>
            </div>
            <span className="badge badge-success">Completado</span>
          </div>
        ) : (
          <p className="text-muted">No hay backups registrados</p>
        )}
      </div>

      <div className="card p-6 border-border bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800">
        <h4 className="font-medium text-red-900 dark:text-red-300 mb-2 flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          Restauración
        </h4>
        <p className="text-sm text-red-700 dark:text-red-400 mb-4">
          La restauración sobrescribe la base de datos actual. Use con precaución.
        </p>
        <button
          onClick={handleRestore}
          className="btn-danger flex items-center gap-2"
        >
          <Database className="w-4 h-4" />
          Restaurar desde Archivo
        </button>
      </div>

      <div className="card p-6">
        <h4 className="font-medium text-heading mb-4">Configuración de Backup Automático</h4>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div>
            <label className="label">Programación (Cron)</label>
            <input value="0 2 * * *" className="input font-mono" readOnly />
            <p className="text-sm text-muted mt-1">Diario a las 02:00 AM</p>
          </div>
          <div>
            <label className="label">Retención</label>
            <input value="30 días" className="input" readOnly />
            <p className="text-sm text-muted mt-1">Se eliminan backups mayores a 30 días</p>
          </div>
          <div>
            <label className="label">Ubicación</label>
            <input value="./backups (volumen Docker)" className="input" readOnly />
          </div>
          <div>
            <label className="label">Formato</label>
            <input value="SQL comprimido (.sql.gz) + volúmenes (.tar.gz)" className="input" readOnly />
          </div>
        </div>
      </div>
    </div>
  )
}