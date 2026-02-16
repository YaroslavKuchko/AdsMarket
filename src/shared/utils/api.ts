export class ApiError extends Error {
  status: number
  bodyText?: string

  constructor(status: number, message: string, bodyText?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.bodyText = bodyText
  }
}

export async function postJson<TResponse>(
  url: string,
  body: unknown,
  init?: Omit<RequestInit, 'method' | 'body'>,
): Promise<TResponse> {
  const jsonBody = JSON.stringify(body)
  // Merge headers properly - init.headers should not overwrite content-type
  const headers = {
    'content-type': 'application/json',
    ...(init?.headers ?? {}),
  }
  
  // Extract headers from init to avoid double-setting
  const { headers: _, ...restInit } = init ?? {}
  
  console.log('[API] POST request:', url)
  console.log('[API] Headers:', JSON.stringify(headers))
  console.log('[API] Body:', jsonBody)
  
  const res = await fetch(url, {
    ...restInit,
    method: 'POST',
    headers,
    body: jsonBody,
  })

  console.log('[API] Response status:', res.status)

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    console.log('[API] Error response body:', text)
    throw new ApiError(res.status, `HTTP ${res.status}`, text || res.statusText)
  }

  return (await res.json()) as TResponse
}

export async function putJson<TResponse>(
  url: string,
  body: unknown,
  init?: Omit<RequestInit, 'method' | 'body'>,
): Promise<TResponse> {
  const jsonBody = JSON.stringify(body)
  const headers = {
    'content-type': 'application/json',
    ...(init?.headers ?? {}),
  }
  const { headers: _, ...restInit } = init ?? {}

  const res = await fetch(url, {
    ...restInit,
    method: 'PUT',
    headers,
    body: jsonBody,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, `HTTP ${res.status}`, text || res.statusText)
  }

  return (await res.json()) as TResponse
}

export async function getJson<TResponse>(
  url: string,
  init?: Omit<RequestInit, 'method'>,
): Promise<TResponse> {
  const res = await fetch(url, {
    method: 'GET',
    headers: {
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new ApiError(res.status, `HTTP ${res.status}`, text || res.statusText)
  }

  return (await res.json()) as TResponse
}


