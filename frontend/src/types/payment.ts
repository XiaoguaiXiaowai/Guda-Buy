export type PaymentChannel = 'ALIPAY_MOCK' | 'WECHAT_MOCK' | 'BALANCE_MOCK'

export type PaymentStatus = 'PENDING' | 'SUCCESS' | 'FAILED' | 'CLOSED'

export type PaymentCallbackStatus = 'SUCCESS' | 'FAILED'

export interface PaymentCashier {
  payment_no: string
  order_no: string
  channel: PaymentChannel
  channel_text: string
  amount: string
  status: PaymentStatus
  status_text: string
  sign: string
  callback_url: string
  order_pay_expires_at: string
  demo_notice: string
}

export interface PaymentCallbackPayload {
  payment_no: string
  amount: string
  status: PaymentCallbackStatus
  signature: string
  transaction_ref?: string
}

export interface PaymentCallbackResult {
  payment_no: string
  order_no: string
  status: PaymentStatus
  status_text: string
  order_status: string
  order_status_text: string
  paid_at: string | null
}
