import http from '@/api/http'
import type {
  Address,
  AddressPayload,
  AuthResponse,
  LoginPayload,
  ProfileUpdatePayload,
  RegisterPayload,
  UserProfile,
} from '@/types/user'

export async function sendEmailCode(email: string): Promise<void> {
  await http.post('/auth/email-code/', { email })
}

export async function register(payload: RegisterPayload): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/register/', payload)
  return data
}

export async function login(payload: LoginPayload): Promise<AuthResponse> {
  const { data } = await http.post<AuthResponse>('/auth/login/', payload)
  return data
}

export async function logout(): Promise<void> {
  await http.post('/auth/logout/')
}

export async function requestPasswordReset(email: string): Promise<void> {
  await http.post('/auth/password/reset/', { email })
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await http.post('/auth/password/reset/confirm/', { token, new_password: newPassword })
}

export async function fetchMe(): Promise<UserProfile> {
  const { data } = await http.get<UserProfile>('/users/me/')
  return data
}

export async function updateMe(payload: ProfileUpdatePayload): Promise<UserProfile> {
  const { data } = await http.patch<UserProfile>('/users/me/', payload)
  return data
}

export async function uploadAvatar(file: File): Promise<UserProfile> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await http.post<UserProfile>('/users/me/avatar/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function listAddresses(): Promise<Address[]> {
  const { data } = await http.get<Address[]>('/users/me/addresses/')
  return data
}

export async function createAddress(payload: AddressPayload): Promise<Address> {
  const { data } = await http.post<Address>('/users/me/addresses/', payload)
  return data
}

export async function updateAddress(
  publicId: string,
  payload: AddressPayload,
): Promise<Address> {
  const { data } = await http.put<Address>(`/users/me/addresses/${publicId}/`, payload)
  return data
}

export async function deleteAddress(publicId: string): Promise<void> {
  await http.delete(`/users/me/addresses/${publicId}/`)
}

export async function setDefaultAddress(publicId: string): Promise<Address> {
  const { data } = await http.post<Address>(`/users/me/addresses/${publicId}/default/`)
  return data
}
