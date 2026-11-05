export interface Documento {
  id: string
  correlativo: string
  tipo_doc_codigo: string
  tipo_documento: string  // alias for compatibility
  oficina_origen_sigla: string
  oficina_origen: string  // alias for compatibility
  oficina_destino_sigla: string
  oficina_destino: string  // alias for compatibility
  fecha_documento: string
  fecha_recepcion?: string
  remitente_id?: string
  remitente?: string  // alias for compatibility
  destinatario_id?: string
  destinatario?: string  // alias for compatibility
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
  created_at: string  // alias for compatibility
  actualizado_en?: string
  updated_at?: string  // alias for compatibility
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