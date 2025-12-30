import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { apiClient } from '@/api/client'
import { Login } from '@/pages/Login'

describe('Login page', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows verification code fields when email verification is required', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        success: true,
        data: { require_email_verification: true },
      },
    } as any)

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login />} />
        </Routes>
      </MemoryRouter>
    )

    await userEvent.click(screen.getByRole('button', { name: '立即注册' }))

    expect(await screen.findByText('邮箱')).toBeInTheDocument()
    expect(await screen.findByText('验证码')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: '发送验证码' })).toBeInTheDocument()
  })

  it('does not show verification code fields when email verification is not required', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
      data: {
        success: true,
        data: { require_email_verification: false },
      },
    } as any)

    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<Login />} />
        </Routes>
      </MemoryRouter>
    )

    await userEvent.click(screen.getByRole('button', { name: '立即注册' }))

    expect(await screen.findByText('邮箱（可选）')).toBeInTheDocument()
    expect(screen.queryByText('验证码')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '发送验证码' })).not.toBeInTheDocument()
  })
})
