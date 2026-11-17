import http from '@/api/http'
import type {
  PaymentCallbackPayload,
  PaymentCallbackResult,
  PaymentCashier,
  PaymentChannel,
} from '@/types/payment'

export async function startMockPayment(
  orderNo: string,
  channel: PaymentChannel,
): Promise<PaymentCashier> {
  const { data } = await http.post<PaymentCashier>(`/payments/${orderNo}/mock-pay/`, { channel })
  return data
}

export async function submitPaymentCallback(
  payload: PaymentCallbackPayload,
): Promise<PaymentCallbackResult> {
  const { data } = await http.post<PaymentCallbackResult>('/payments/callback/', payload)
  return data
}
