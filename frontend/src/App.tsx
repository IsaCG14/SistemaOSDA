import { Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { DocumentosPage } from './pages/DocumentosPage'
import { DocumentoDetailPage } from './pages/DocumentoDetailPage'
import { OficinasPage } from './pages/OficinasPage'
import { TiposDocumentoPage } from './pages/TiposDocumentoPage'
import { PersonasPage } from './pages/PersonasPage'
import { ConsultasPage } from './pages/ConsultasPage'
import { ConfiguracionPage } from './pages/ConfiguracionPage'
import { useAuth } from './hooks/useAuth'
import { LoadingSpinner } from './components/LoadingSpinner'

function PrivateRoute({ children, adminOnly = false }: { children: React.ReactNode, adminOnly?: boolean }) {
  const { user, loading } = useAuth()
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }
  
  if (!user) {
    return <Navigate to="/login" replace />
  }
  
  if (adminOnly && user.role !== 'ADMIN') {
    return <Navigate to="/dashboard" replace />
  }
  
  return <>{children}</>
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/documentos" element={<DocumentosPage />} />
        <Route path="/documentos/:id" element={<DocumentoDetailPage />} />
        <Route path="/oficinas" element={<OficinasPage />} />
        <Route path="/tipos-documento" element={<TiposDocumentoPage />} />
        <Route path="/usuarios" element={<PrivateRoute adminOnly><PersonasPage /></PrivateRoute>} />
        <Route path="/personas" element={<Navigate to="/usuarios" replace />} />
        <Route path="/consultas" element={<ConsultasPage />} />
        <Route path="/configuracion" element={<ConfiguracionPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}