import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThresholdView } from '../components/ThresholdView';
import { api } from '../api/client';

vi.mock('../api/client', () => ({
  api: {
    getThresholds: vi.fn(),
    updateThreshold: vi.fn(),
    setCsrfToken: vi.fn(),
    getCsrfToken: vi.fn()
  }
}));

const mockThresholds = [
  { id: 't-1', config_key: 'anomaly_threshold', config_value: 0.50, description: 'Minimum score to classify a log as anomalous', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T10:00:00' },
  { id: 't-2', config_key: 'severity_critical', config_value: 0.85, description: 'Score boundary for CRITICAL severity', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T10:00:00' },
  { id: 't-3', config_key: 'severity_high', config_value: 0.70, description: 'Score boundary for HIGH severity', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T10:00:00' },
  { id: 't-4', config_key: 'level_critical_weight', config_value: 0.40, description: 'Base score addition for CRITICAL log level', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T10:00:00' },
];

describe('ThresholdView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getThresholds).mockResolvedValue(mockThresholds);
  });

  it('renders threshold configuration table with data', async () => {
    render(<ThresholdView canMutate={true} />);
    await waitFor(() => {
      expect(screen.getByText('Detection Threshold Configuration')).toBeInTheDocument();
      const cells = screen.getAllByText('anomaly_threshold');
      expect(cells.length).toBeGreaterThan(0);
      expect(screen.getByText('severity_critical')).toBeInTheDocument();
      expect(screen.getByText('severity_high')).toBeInTheDocument();
      expect(screen.getByText('level_critical_weight')).toBeInTheDocument();
    });
  });

  it('shows current values formatted to 4 decimal places', async () => {
    render(<ThresholdView canMutate={true} />);
    await waitFor(() => {
      expect(screen.getByText('0.5000')).toBeInTheDocument();
      expect(screen.getByText('0.8500')).toBeInTheDocument();
      expect(screen.getByText('0.7000')).toBeInTheDocument();
      expect(screen.getByText('0.4000')).toBeInTheDocument();
    });
  });

  it('shows input fields and save buttons when canMutate is true', async () => {
    render(<ThresholdView canMutate={true} />);
    await waitFor(() => {
      const inputs = screen.getAllByRole('spinbutton');
      expect(inputs.length).toBeGreaterThan(0);
      const saveButtons = screen.getAllByRole('button');
      const enabledSaves = saveButtons.filter(b => !b.disabled);
      expect(enabledSaves.length).toBeGreaterThan(0);
    });
  });

  it('hides input fields and save buttons when viewer role', async () => {
    render(<ThresholdView canMutate={false} />);
    await waitFor(() => {
      const inputs = screen.queryAllByRole('spinbutton');
      expect(inputs.length).toBe(0);
      const saveButtons = screen.getAllByRole('button');
      const enabledSaves = saveButtons.filter(b => !b.disabled && b.textContent === '');
      expect(enabledSaves.length).toBe(0);
    });
  });

  it('calls updateThreshold when save clicked with new value', async () => {
    vi.mocked(api.updateThreshold).mockResolvedValue({
      id: 't-1', config_key: 'anomaly_threshold', config_value: 0.60, description: 'Minimum score to classify a log as anomalous', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T11:00:00'
    });
    // First fetch returns old values, second fetch (after save) returns new values
    vi.mocked(api.getThresholds)
      .mockResolvedValueOnce(mockThresholds)
      .mockResolvedValue([
        { id: 't-1', config_key: 'anomaly_threshold', config_value: 0.60, description: 'Minimum score to classify a log as anomalous', created_at: '2026-10-15T10:00:00', updated_at: '2026-10-15T11:00:00' },
        ...mockThresholds.slice(1)
      ]);

    render(<ThresholdView canMutate={true} />);
    await waitFor(() => {
      const cells = screen.getAllByText('anomaly_threshold');
      expect(cells.length).toBeGreaterThan(0);
    });

    const anomalyRow = screen.getAllByText('anomaly_threshold')[0].closest('tr');
    const input = anomalyRow?.querySelector('input[type="number"]') as HTMLInputElement;
    expect(input).toBeInTheDocument();

    await userEvent.clear(input!);
    await userEvent.type(input!, '0.60');

    const saveBtn = anomalyRow?.querySelector('button') as HTMLButtonElement;
    expect(saveBtn).not.toBeDisabled();
    await userEvent.click(saveBtn!);

    await waitFor(() => expect(api.updateThreshold).toHaveBeenCalledWith('anomaly_threshold', 0.60));
  });

  it('disables save button when value unchanged', async () => {
    render(<ThresholdView canMutate={true} />);
    await waitFor(() => {
      const cells = screen.getAllByText('anomaly_threshold');
      const anomalyRow = cells[0].closest('tr');
      const saveBtn = anomalyRow?.querySelector('button') as HTMLButtonElement;
      expect(saveBtn).toBeDisabled();
    });
  });

  it('shows error message on fetch failure', async () => {
    vi.mocked(api.getThresholds).mockRejectedValue(new Error('Failed to fetch thresholds'));
    render(<ThresholdView canMutate={true} />);
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch thresholds')).toBeInTheDocument();
    });
  });

  it('shows usage notes section', async () => {
    render(<ThresholdView canMutate={true} />);
    await waitFor(() => {
      const usageNotes = screen.getByText(/about detection thresholds/i).closest('div');
      expect(usageNotes).toBeInTheDocument();
      expect(usageNotes).toHaveTextContent(/anomaly_threshold/i);
      expect(usageNotes).toHaveTextContent(/severity_critical/i);
      expect(usageNotes).toHaveTextContent(/level_.*_weight/i);
      expect(usageNotes).toHaveTextContent(/rarity_/i);
      expect(usageNotes).toHaveTextContent(/burst_/i);
      expect(usageNotes).toHaveTextContent(/entropy_/i);
    });
  });
});

