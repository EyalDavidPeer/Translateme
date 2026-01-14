import { useState, useEffect, useCallback } from 'react';
import type { JobStatus, JobResult, JobConfig } from '../types';
import { createJob, getJobStatus, getJobResult } from '../api/client';

interface UseJobReturn {
  jobId: string | null;
  status: JobStatus | null;
  result: JobResult | null;
  isLoading: boolean;
  error: string | null;
  startJob: (file: File, config: JobConfig) => Promise<void>;
  reset: () => void;
}

export function useJob(): UseJobReturn {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll for status while job is processing
  useEffect(() => {
    if (!jobId || status?.status === 'completed' || status?.status === 'failed') {
      return;
    }

    const interval = setInterval(async () => {
      try {
        const newStatus = await getJobStatus(jobId);
        setStatus(newStatus);

        if (newStatus.status === 'completed') {
          const jobResult = await getJobResult(jobId);
          setResult(jobResult);
          setIsLoading(false);
        } else if (newStatus.status === 'failed') {
          setError(newStatus.error || 'Job failed');
          setIsLoading(false);
        }
      } catch (err) {
        console.error('Error polling job status:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, status?.status]);

  const startJob = useCallback(async (file: File, config: JobConfig) => {
    setIsLoading(true);
    setError(null);
    setResult(null);
    setStatus(null);

    try {
      const { job_id } = await createJob(file, config);
      setJobId(job_id);
      setStatus({
        job_id,
        status: 'pending',
        progress: 0,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start job');
      setIsLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setJobId(null);
    setStatus(null);
    setResult(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return {
    jobId,
    status,
    result,
    isLoading,
    error,
    startJob,
    reset,
  };
}
