import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'
import { 
  Users, Plus, Edit, Trash2, Search, Loader2,
  Building2, Mail, Phone, XCircle
} from 'lucide-react'
import { Persona } from '../types'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'

export function PersonasPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [oficinaFiltro, setOficinaFiltro] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingPersona, setEditingPersona] = useState<Persona | null>(null)
  const [formData, setFormData] = useState({
    id: '',
    nombre: '',
    cargo: '',
    oficina_sigla: '',
    telegram_user_id: '',
  })

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
    mutationFn: async (data: Partial<Persona>) => {
      const resp = await api.post('/personas', data)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personas'] })
      setShowModal(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (data: Partial<Persona> & { id: string }) => {
      const { id, ...rest } = data
      const resp = await api.put(`/personas/${id}`, rest)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personas'] })
      setShowModal(false)
      setEditingPersona(null)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/personas/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['personas'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data = {
      ...formData,
      telegram_user_id: formData.telegram_user_id ? parseInt(formData.telegram_user_id) : undefined,
    }
    if (editingPersona) {
      updateMutation.mutate({ ...data, id: editingPersona.id })
    } else {
      createMutation.mutate(data)
    }
  }

  const resetForm = () => {
    setFormData({ id: '', nombre: '', cargo: '', oficina_sigla: '', telegram_user_id: '' })
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
      cargo: persona.cargo || '',
      oficina_sigla: persona.oficina_sigla || '',
      telegram_user_id: persona.telegram_user_id?.toString() || '',
    })
    setShowModal(true)
  }

  const filteredPersonas = personas?.filter(p => 
    p.nombre.toLowerCase().includes(search.toLowerCase()) ||
    p.cargo?.toLowerCase().includes(search.toLowerCase())
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
          <h1 className="text-2xl font-bold text-heading">Personas</h1>
          <p className="text-muted mt-1">Directorio de remitentes, destinatarios y usuarios</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nueva Persona
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
              placeholder="Buscar por nombre, cargo..."
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
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Cargo</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Oficina</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Telegram ID</th>
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
                  <td className="px-4 py-3 text-sm text-muted">{persona.cargo || '-'}</td>
                  <td className="px-4 py-3 text-sm text-muted">
                    {persona.oficina_sigla ? (
                      <span className="badge badge-info">{persona.oficina_sigla}</span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted font-mono">
                    {persona.telegram_user_id || '-'}
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
                  <td colSpan={5} className="px-4 py-12 text-center">
                    <EmptyState
                      icon={Users}
                      title="No hay personas"
                      description={search ? 'No se encontraron personas con ese filtro' : 'Comience agregando la primera persona'}
                      action={<button onClick={openCreate} className="btn-primary">Agregar persona</button>}
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
          <div className="bg-card rounded-xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4 border-b border-default pb-4">
              <h2 className="text-xl font-semibold text-heading">
                {editingPersona ? 'Editar Persona' : 'Nueva Persona'}
              </h2>
              <button onClick={() => { setShowModal(false); resetForm(); }} className="text-muted hover:text-heading">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
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