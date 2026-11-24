import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { api } from '../api'

interface User {
  id: string
  email: string
  role: 'ADMIN' | 'SECRETARIO'
  nombre: string
  oficina_sigla: string | null
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  loading: boolean
  login: (identifier: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Verificar sesión existente
    const token = localStorage.getItem('access_token')
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      verifyToken()
    } else {
      setLoading(false)
    }

    // Escuchar evento de logout desde api interceptor
    const handleLogout = () => {
      localStorage.removeItem('access_token')
      delete api.defaults.headers.common['Authorization']
      setUser(null)
    }
    
    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [])

  const verifyToken = async () => {
    try {
      const response = await api.get('/auth/v1/user')
      const userData = response.data
      console.log('verifyToken response:', userData)
      
      // Extraer role de user_metadata (GoTrue lo pone ahí)
      const userRole = userData.user_metadata?.role || userData.role || 'SECRETARIO'
      
      // Si no es ADMIN, buscar oficina usando el nuevo endpoint público
      let oficina_sigla = null
      let nombre_usuario = ''
      if (userRole !== 'ADMIN' && userData.email) {
        try {
          const oficinaResp = await api.get('/personas/me/oficina')
          if (oficinaResp.data) {
            oficina_sigla = oficinaResp.data.oficina_sigla
            nombre_usuario = oficinaResp.data.nombre || ''
          }
        } catch {
          // Si falla, intentar método anterior como fallback
          const personaResp = await api.get(`/personas?email=eq.${userData.email}&select=oficina_sigla,nombre,activa`)
          if (personaResp.data?.[0]) {
            oficina_sigla = personaResp.data[0].oficina_sigla
            nombre_usuario = personaResp.data[0].nombre || ''
          }
        }
      }
      
      // Extraer nombre de user_metadata (GoTrue lo pone ahí)
      const nombre = nombre_usuario || userData.user_metadata?.nombre || userData.nombre || ''
      // userRole ya definido arriba
      
      setUser({ ...userData, nombre, oficina_sigla, role: userRole })
    } catch (err) {
      console.error('verifyToken failed:', err)
      // NO eliminar token automáticamente - dejar que el interceptor 401 lo maneje
      // localStorage.removeItem('access_token')
      // delete api.defaults.headers.common['Authorization']
    } finally {
      setLoading(false)
    }
  }

  const login = async (identifier: string, password: string) => {
            // Si el identificador contiene @, es un email; si no, buscar email por username en personas
            const isEmail = identifier.includes('@')

            let emailToUse = identifier

            if (!isEmail) {
              // Buscar email por username usando endpoint público (sin autenticación)
              try {
                const personaResp = await api.get(`/personas/username/${identifier}/email`)
                if (personaResp.data && personaResp.data.email) {
                  emailToUse = personaResp.data.email
                }
              } catch (err) {
                console.error('Error buscando email por username:', err)
              }
            }

            console.log('Login attempt with:', { email: emailToUse })
            const response = await api.post('/auth/v1/token?grant_type=password', { email: emailToUse, password })
            console.log('Login response:', response.data)
            const { access_token, user: userData } = response.data

        localStorage.setItem('access_token', access_token)
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
      
      // Extraer role de user_metadata (GoTrue lo pone ahí)
      const userRole = userData.user_metadata?.role || userData.role || 'SECRETARIO'

      // Si no es ADMIN, buscar oficina usando el nuevo endpoint público
      let oficina_sigla = null
      let nombre_usuario = ''
      if (userRole !== 'ADMIN' && userData.email) {
        try {
          const oficinaResp = await api.get('/personas/me/oficina')
          if (oficinaResp.data) {
            oficina_sigla = oficinaResp.data.oficina_sigla
            nombre_usuario = oficinaResp.data.nombre || ''
          }
        } catch {
          // Fallback
          const personaResp = await api.get(`/personas?email=eq.${userData.email}&select=oficina_sigla,nombre,activa`)
          if (personaResp.data?.[0]) {
            oficina_sigla = personaResp.data[0].oficina_sigla
            nombre_usuario = personaResp.data[0].nombre || ''
          }
        }
      }
      
      // Extraer nombre de user_metadata (GoTrue lo pone ahí)
      const nombre = nombre_usuario || userData.user_metadata?.nombre || userData.nombre || ''
      // userRole ya definido arriba
      
      setUser({ ...userData, nombre, oficina_sigla, role: userRole })
    }

  const logout = () => {
    localStorage.removeItem('access_token')
    delete api.defaults.headers.common['Authorization']
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, isAuthenticated: !!user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}