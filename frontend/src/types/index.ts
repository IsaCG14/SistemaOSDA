export interface Documento {
  id: string
  correlativo: string
  tipo_doc_codigo: string
  /** @deprecated Use `tipo_doc_codigo` instead */
  tipo_documento: string
  oficina_origen_sigla: string
  /** @deprecated Use `oficina_origen_sigla` instead */
  oficina_origen: string
  oficina_destino_sigla: string
  /** @deprecated Use `oficina_destino_sigla` instead */
  oficina_destino: string
  fecha_documento: string
  fecha_recepcion?: string
  remitente_id?: string
  /** @deprecated Use `remitente_id` instead */
  remitente?: string
  destinatario_id?: string
  /** @deprecated Use `destinatario_id` instead */
  destinatario?: string
  asunto?: string
  folios?: number
  anexos?: string[]
  estado: string
  prioridad?: string
  observaciones?: string
  confianza_ocr?: number
  confirmado_por?: string
  confirmado_en?: string
  creado_en: string
  /** @deprecated Use `creado_en` instead */
  created_at: string
  actualizado_en?: string
  /** @deprecated Use `actualizado_en` instead */
  updated_at?: string
}

export interface Oficina {
  sigla: string
  nombre: string
  activa: boolean
}

export interface Persona {
  id: string
  nombre: string
  cargo?: string
  oficina_sigla?: string
  telegram_user_id?: number
  username?: string
  email?: string
  activa?: boolean
  role?: 'ADMIN' | 'SECRETARIO'
}

export interface TipoDocumento {
  codigo: string
  nombre: string
  prefijo_correlativo: string
  regla_secuencial: Record<string, any>
  plazo_dias_respuesta: number
  requiere_anexos: boolean
}

export interface TraceResult {
  documento: Documento
  respuestas: Documento[]
  referencias: Documento[]
  anexos: Documento[]
  flujo_oficinas: any[]
}