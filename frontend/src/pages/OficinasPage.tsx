import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'
import { 
  Building2, Plus, Edit, Trash2, Search, CheckCircle, XCircle,
  Loader2
} from 'lucide-react'
import { Oficina } from '../types'
import { LoadingSpinner } from '../components/LoadingSpinner'
import { EmptyState } from '../components/EmptyState'

export function OficinasPage() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingOficina, setEditingOficina] = useState<Oficina | null>(null)
  const [formData, setFormData] = useState({ sigla: '', nombre: '', activa: true })

  const { data: oficinas, isLoading } = useQuery({
    queryKey: ['oficinas'],
    queryFn: async () => {
      const resp = await api.get('/oficinas')
      return resp.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async (data: Partial<Oficina>) => {
      const resp = await api.post('/oficinas', data)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oficinas'] })
      setShowModal(false)
      resetForm()
    },
  })

  const updateMutation = useMutation({
    mutationFn: async (data: Partial<Oficina> & { id: string }) => {
      const { id, ...rest } = data
      const resp = await api.put(`/oficinas/${id}`, rest)
      return resp.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oficinas'] })
      setShowModal(false)
      setEditingOficina(null)
      resetForm()
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/oficinas/${id}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['oficinas'] })
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (editingOficina) {
      updateMutation.mutate({ ...formData, id: editingOficina.sigla })
    } else {
      createMutation.mutate(formData)
    }
  }

  const resetForm = () => {
    setFormData({ sigla: '', nombre: '', activa: true })
    setEditingOficina(null)
  }

  const openCreate = () => {
    resetForm()
    setShowModal(true)
  }

  const openEdit = (oficina: Oficina) => {
    setEditingOficina(oficina)
    setFormData({ sigla: oficina.sigla, nombre: oficina.nombre, activa: oficina.activa })
    setShowModal(true)
  }

  const filteredOficinas = oficinas?.filter(o => 
    o.sigla.toLowerCase().includes(search.toLowerCase()) ||
    o.nombre.toLowerCase().includes(search.toLowerCase())
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
          <h1 className="text-2xl font-bold text-heading">Oficinas</h1>
          <p className="text-muted mt-1">Catálogo de oficinas y dependencias</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Nueva Oficina
        </button>
      </div>

      {/* Búsqueda */}
      <div className="card p-4">
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="label">Buscar</label>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input"
              placeholder="Buscar por sigla o nombre..."
            />
          </div>
        </div>
      </div>

      {/* Tabla */}
      <div className="card">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-default">
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Sigla</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Nombre</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Estado</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-muted uppercase">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default">
              {filteredOficinas.map((oficina: Oficina) => (
                <tr key={oficina.sigla} className="card-hover">
                  <td className="px-4 py-3">
                    <code className="text-sm font-mono text-heading">{oficina.sigla}</code>
                  </td>
                  <td className="px-4 py-3 text-sm text-heading">{oficina.nombre}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${oficina.activa ? 'badge-success' : 'badge-gray'}`}>
                      {oficina.activa ? 'Activa' : 'Inactiva'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => openEdit(oficina)}
                        className="p-2 rounded-lg btn-ghost"
                        aria-label="Editar"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(oficina.sigla)}
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
              {!filteredOficinas.length && (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center">
                    <EmptyState
                      icon={Building2}
                      title="No hay oficinas"
                      description={search ? 'No se encontraron oficinas con ese filtro' : 'Comience creando la primera oficina'}
                      action={<button onClick={openCreate} className="btn-primary">Crear oficina</button>}
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
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold text-heading">
                {editingOficina ? 'Editar Oficina' : 'Nueva Oficina'}
              </h2>
              <button onClick={() => { setShowModal(false); resetForm(); }} className="text-muted hover:text-heading">
                <XCircle className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Sigla</label>
                <input
                  type="text"
                  value={formData.sigla}
                  onChange={(e) => setFormData({ ...formData, sigla: e.target.value.toUpperCase() })}
                  className="input"
                  placeholder="OTIC"
                  maxLength={10}
                  disabled={!!editingOficina}
                  required
                />
              </div>
              <div>
                <label className="label">Nombre</label>
                <input
                  type="text"
                  value={formData.nombre}
                  onChange={(e) => setFormData({ ...formData, nombre: e.target.value })}
                  className="input"
                  placeholder="Oficina de Tecnología..."
                  required
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="activa"
                  checked={formData.activa}
                  onChange={(e) => setFormData({ ...formData, activa: e.target.checked })}
                  className="w-4 h-4 text-blue-600 rounded border-default"
                />
                <label htmlFor="activa" className="text-sm text-muted">Activa</label>
              </div>
              <div className="flex gap-2 pt-4">
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