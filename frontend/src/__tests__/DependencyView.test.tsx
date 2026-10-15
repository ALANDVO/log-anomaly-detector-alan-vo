import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DependencyView } from '../components/DependencyView';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getDependencies: vi.fn(),
    createDependency: vi.fn(),
    updateDependency: vi.fn(),
    deleteDependency: vi.fn(),
    setCsrfToken: vi.fn(),
    getCsrfToken: vi.fn()
  }
}));

const mockDeps = [
  { id: 'dep-1', upstream: 'db-proxy', downstream: 'auth-service', relationship: 'depends_on', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T10:00:00' },
  { id: 'dep-2', upstream: 'cache-layer', downstream: 'api-gateway', relationship: 'depends_on', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T10:00:00' },
];

describe('DependencyView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getDependencies).mockResolvedValue(mockDeps);
  });

  it('renders dependency list with upstream and downstream services', async () => {
    render(<DependencyView canMutate={true} />);
    await waitFor(() => {
      expect(screen.getByText('Service Dependency Topology')).toBeInTheDocument();
      expect(screen.getByText('db-proxy')).toBeInTheDocument();
      expect(screen.getByText('auth-service')).toBeInTheDocument();
      expect(screen.getByText('cache-layer')).toBeInTheDocument();
      expect(screen.getByText('api-gateway')).toBeInTheDocument();
    });
  });

  it('shows create form when Add Dependency clicked', async () => {
    render(<DependencyView canMutate={true} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add dependency/i })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole('button', { name: /add dependency/i }));
    expect(screen.getByPlaceholderText(/upstream service/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/downstream service/i)).toBeInTheDocument();
  });

  it('calls createDependency when form submitted', async () => {
    vi.mocked(api.createDependency).mockResolvedValue({
      id: 'dep-new', upstream: 'new-svc', downstream: 'target-svc', relationship: 'calls',
      created_at: '2026-10-15T11:00:00', updated_at: '2026-10-15T11:00:00'
    });
    vi.mocked(api.getDependencies).mockResolvedValue([...mockDeps, { id: 'dep-new', upstream: 'new-svc', downstream: 'target-svc', relationship: 'calls', created_at: '2026-10-15T11:00:00', updated_at: '2026-10-15T11:00:00' }]);

    render(<DependencyView canMutate={true} />);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /add dependency/i })).toBeInTheDocument();
    });
    await userEvent.click(screen.getByRole('button', { name: /add dependency/i }));
    await userEvent.type(screen.getByPlaceholderText(/upstream service/i), 'new-svc');
    await userEvent.type(screen.getByPlaceholderText(/downstream service/i), 'target-svc');
    const relInput = screen.getByPlaceholderText(/relationship/i);
    await userEvent.clear(relInput);
    await userEvent.type(relInput, 'calls');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));
    await waitFor(() => expect(api.createDependency).toHaveBeenCalledWith({
      upstream: 'new-svc', downstream: 'target-svc', relationship: 'calls'
    }));
  });

  it('hides create button when viewer role', async () => {
    render(<DependencyView canMutate={false} />);
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /add dependency/i })).not.toBeInTheDocument();
    });
  });

  it('shows usage notes section', async () => {
    render(<DependencyView canMutate={true} />);
    await waitFor(() => {
      expect(screen.getByText(/usage notes/i)).toBeInTheDocument();
      expect(screen.getByText(/upstream services are dependencies/i)).toBeInTheDocument();
    });
  });
});