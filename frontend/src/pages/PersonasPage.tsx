import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { 
  Users, Plus, Edit, Trash2, Search, Loader2,
  Building2, Mail, Phone, XCircle, Lock, Key, Shield
} from 'lucide-react'
import { Persona } from '../types'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'
import { AlertCircle } from 'lucide-react'

interface UsuarioFormData {
  id: string
  nombre: string
  email: string
  password: string
  cargo: string
  oficina_sigla: string
  telegram_user_id: string | number
  username: string
  role: 'ADMIN' | 'SECRETARIO'
  activa: boolean
}

export function PersonasPage() {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const isAdmin = user?.role === 'ADMIN'
  const [search, setSearch] = useState('')
  const [oficinaFiltro, setOficinaFiltro] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null)
  const [formData, setFormData] = useState<UsuarioFormData>({
    id: '',
    nombre: '',
    email: '',
    password: '',
    cargo: '',
    oficina_sigla: '',
    telegram_user_id: '',
    username: '',
    role: 'SECRETARIO',
    activa: true,
  })

  // Solo permitir acceso a ADMIN
  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="card p-8 text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-heading mb-2">Acceso denegado</h2>
          <p className="text-muted">Solo los administradores pueden gestionar usuarios.</p>
        </div>
      </div>
    )
  }

  const { data: personas, isLoading } = useQuery({
    queryKey: ['personas', oficinaFiltro],
    queryFn: async () => {
      const params = new URLSearchParams()
      if (oficinaFiltro) params.append('oficina_sigla', oficinaFiltro)
      const resp = await api.get(`/personas?${params}`)
      return resp.data
    },
  })

  const { data: oficinas } = useQuery({
    queryKey: ['oficinas-select'],
    queryFn: async () => {
      const resp = await api.get('/oficinas?activas=true')
      return resp.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async (data: UsuarioFormData) => {
      const { id, ...rest } = data
      const resp = await api.post('/usuarios', rest)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personas'] })
      setShowModal(false)
      resetForm()
    },
    onError: (error: any) => {
      console.error('Error creando usuario:', error)
      alert(`Error al crear usuario: ${error?.response?.data?.detail || error?.message || 'Error desconocido'}`)
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (data: UsuarioFormData & { id: string }) => {
      const { id, ...rest } = data
      // No enviar password vacío al actualizar
      if (!rest.password) {
        delete rest.password
      }
      const resp = await api.patch(`/usuarios/${id}`, rest)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personas'] })
      setShowModal(false)
      setEditingPersona(null)
      resetForm()
    },
    onError: (error: any) => {
      console.error('Error actualizando usuario:', error)
      alert(`Error al actualizar usuario: ${error?.response?.data?.detail || error?.message || 'Error desconocido'}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/usuarios/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personas'] })
    },
    onError: (error: any) => {
      console.error('Error eliminando usuario:', error)
      alert(`Error al eliminar usuario: ${error?.response?.data?.detail || error?.message || 'Error desconocido'}`)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data = {
      ...formData,
      telegram_user_id: formData.telegram_user_id ? parseInt(formData.telegram_user_id.toString()) : undefined,
      activa: formData.activa,
    }
    if (editingPersona) {
      updateMutation.mutate({ ...data, id: editingPersona.id })
    } else {
      createMutation.mutate(data)
    }
  }

  const resetForm = () => {
    setFormData({ 
      id: '', 
      nombre: '', 
      email: '', 
      password: '', 
      cargo: '', 
      oficina_sigla: '', 
      telegram_user_id: '', 
      username: '', 
      role: 'SECRETARIO',
      activa: true,
    })
    setEditingPersona(null)
  }

  const openCreate = () => {
    resetForm()
    setShowModal(true)
  }

  const openEdit = (persona: Persona) => {
    setEditingPersona(persona)
    setFormData({
      id: persona.id,
      nombre: persona.nombre,
      email: persona.email || '',
      password: '', // No mostrar password actual por seguridad
      cargo: persona.cargo || '',
      oficina_sigla: persona.oficina_sigla || '',
      telegram_user_id: persona.telegram_user_id?.toString() || '',
      username: persona.username || '',
      role: persona.role || 'SECRETARIO',
      activa: persona.activa ?? true,
    })
    setShowModal(true)
  }

  const filteredPersonas = personas?.filter(p => 
    p.nombre.toLowerCase().includes(search.toLowerCase()) ||
    p.cargo?.toLowerCase().includes(search.toLowerCase()) ||
    p.username?.toLowerCase().includes(search.toLowerCase()) ||
    p.email?.toLowerCase().includes(search.toLowerCase())
  ) || []

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6 bg-page">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-heading">Usuarios</h1>
          <p className="text-muted mt-1">Gestión unificada de cuentas y personas</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nuevo Usuario
        </button>
      </div>

      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <label className="label">Buscar</label>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input"
              placeholder="Buscar por nombre, cargo, usuario, email..."
            />
          </div>
          <div className="sm:w-64">
            <label className="label">Filtrar por oficina</label>
            <select
              value={oficinaFiltro}
              onChange={(e) => setOficinaFiltro(e.target.value)}
              className="input"
            >
              <option value="">Todas las oficinas</option>
              {oficinas?.map((o: any) => (
                <option key={o.sigla} value={o.sigla}>{o.sigla} - {o.nombre}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-default">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Nombre</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Email</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Usuario</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Cargo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Oficina</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Rol</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Telegram ID</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Estado</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              {filteredPersonas.map((persona: Persona) => (
                <tr key={persona.id} className="card-hover">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 rounded-full flex items-center justify-center">
                        <span className="text-blue-700 dark:text-blue-400 font-medium text-sm">
                          {persona.nombre.charAt(0).toUpperCase()}
                        </span>
                      </div>
                      <span className="text-sm font-medium text-heading">{persona.nombre}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted font-mono">{persona.email || '-'}</td>
                  <td className="px-4 py-3 text-sm text-muted">{persona.username || '-'}</td>
                  <td className="px-4 py-3 text-sm text-muted">{persona.cargo || '-'}</td>
                  <td className="px-4 py-3 text-sm text-muted">
                    {persona.oficina_sigla ? (
                      <span className="badge badge-info">{persona.oficina_sigla}</span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`badge ${persona.role === 'ADMIN' ? 'badge-danger' : 'badge-primary'}`}>
                      {persona.role || 'SECRETARIO'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-muted font-mono">
                    {persona.telegram_user_id || '-'}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    <span className={persona.activa ? 'badge badge-success' : 'badge badge-gray'}>
                      {persona.activa ? 'Activo' : 'Inactivo'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openEdit(persona)}
                        className="p-2 rounded-lg btn-ghost"
                        aria-label="Editar"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(persona.id)}
                        disabled={deleteMutation.isPending}
                        className="p-2 rounded-lg btn-ghost text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300"
                        aria-label="Eliminar"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!filteredPersonas.length && (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center">
                    <EmptyState
                      icon={Users}
                      title={search ? 'No se encontraron usuarios' : 'No hay usuarios registrados'}
                      description={search ? 'No se encontraron usuarios con ese filtro' : 'Comience agregando el primer usuario'}
                      action={<button onClick={openCreate} className="btn-primary">Agregar usuario</button>}
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-card rounded-xl shadow-xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4 border-b border-default pb-4">
              <h2 className="text-xl font-semibold text-heading">
                {editingPersona ? 'Editar Usuario' : 'Nuevo Usuario'}
              </h2>
              <button onClick={() => { setShowModal(false); resetForm(); }} className="text-muted hover:text-heading">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">ID (UUID)</label>
                  <input
                    type="text"
                    value={formData.id}
                    onChange={(e) => setFormData({ ...formData, id: e.target.value })}
                    className="input"
                    placeholder="Auto-generado si vacío"
                    disabled={!!editingPersona}
                  />
                </div>
                <div>
                  <label className="label">Usuario (para login)</label>
                  <input
                    type="text"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    className="input"
                    placeholder="usuario para login"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Nombre completo</label>
                  <input
                    type="text"
                    value={formData.nombre}
                    onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                    className="input"
                    placeholder="Juan Pérez"
                    required
                  />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="input"
                    placeholder="usuario@ejemplo.gob.ve"
                    required
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">{editingPersona ? 'Nueva contraseña (opcional)' : 'Contraseña'}</label>
                  <div className="relative">
                    <input
                      type="password"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      className="input pr-10"
                      placeholder={editingPersona ? 'Dejar vacío para mantener actual' : '••••••••'}
                      required={!editingPersona}
                    />
                    <Lock className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 w-5 h-5" />
                  </div>
                </div>
                <div>
                  <label className="label">Rol</label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as 'ADMIN' | 'SECRETARIO' })}
                    className="input"
                  >
                    <option value="SECRETARIO">SECRETARIO</option>
                    <option value="ADMIN">ADMIN</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Cargo</label>
                  <input
                    type="text"
                    value={formData.cargo}
                    onChange={(e) => setFormData({ ...formData, cargo: e.target.value })}
                    className="input"
                    placeholder="Analista de Sistemas"
                  />
                </div>
                <div>
                  <label className="label">Oficina</label>
                  <select
                    value={formData.oficina_sigla}
                    onChange={(e) => setFormData({ ...formData, oficina_sigla: e.target.value })}
                    className="input"
                  >
                    <option value="">Sin oficina asignada</option>
                    {oficinas?.map((o: any) => (
                      <option key={o.sigla} value={o.sigla}>{o.sigla} - {o.nombre}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="label">Telegram User ID</label>
                  <input
                    type="number"
                    value={formData.telegram_user_id}
                    onChange={(e) => setFormData({ ...formData, telegram_user_id: e.target.value })}
                    className="input"
                    placeholder="123456789"
                  />
                </div>
                <div>
                  <label className="label">Estado</label>
                  <select
                    value={formData.activa.toString()}
                    onChange={(e) => setFormData({ ...formData, activa: e.target.value === 'true' })}
                    className="input"
                  >
                    <option value="true">Activo</option>
                    <option value="false">Inactivo</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-2 pt-4 border-t border-default">
                <button
                  type="button"
                  onClick={() => { setShowModal(false); resetForm(); }}
                  className="btn-secondary flex-1"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending || updateMutation.isPending}
                  className="btn-primary flex-1"
                >
                  {createMutation.isPending || updateMutation.isPending ? (
                    <span className="flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Guardando...
                    </span>
                  ) : (
                    'Guardar'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}