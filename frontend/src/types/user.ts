export type Gender = 'UNKNOWN' | 'MALE' | 'FEMALE'

export interface UserProfile {
  public_id: string
  username: string
  email: string
  nickname: string
  gender: Gender
  gender_label: string
  birthday: string | null
  avatar: string | null
  created_at: string
}

export interface AuthResponse {
  access: string
  expires_in: number
  user: UserProfile
}

export interface LoginPayload {
  account: string
  password: string
}

export interface RegisterPayload {
  email: string
  username: string
  password: string
  email_code: string
}

export interface ProfileUpdatePayload {
  nickname?: string
  gender?: Gender
  birthday?: string | null
}

export interface Address {
  public_id: string
  receiver_name: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  postal_code: string
  is_default: boolean
}

export interface AddressPayload {
  receiver_name: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  postal_code?: string
  is_default?: boolean
}
