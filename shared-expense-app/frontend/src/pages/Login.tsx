import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { ArrowRightLeft, AlertTriangle } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
});

type LoginSchemaInput = z.infer<typeof loginSchema>;

export const Login: React.FC = () => {
  const { loginAction } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginSchemaInput>({
    resolver: zodResolver(loginSchema),
  });

  const from = location.state?.from?.pathname || '/dashboard';

  const onSubmit = async (data: LoginSchemaInput) => {
    setErrorMsg(null);
    try {
      await loginAction(data.username, data.password);
      navigate(from, { replace: true });
    } catch (e: any) {
      setErrorMsg(
        e.response?.status === 401
          ? 'Invalid username or password. Please try again.'
          : 'Could not connect to the Spreewise server. Make sure the backend is running.'
      );
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 bg-white p-8 border border-slate-200 rounded-2xl shadow-xl">
        {/* Branding header */}
        <div className="flex flex-col items-center">
          <div className="bg-violet-600 p-3 rounded-2xl text-white shadow-lg shadow-violet-600/10">
            <ArrowRightLeft className="h-8 w-8" />
          </div>
          <h2 className="mt-6 text-center text-3xl font-extrabold tracking-tight text-slate-900">
            Spreewise
          </h2>
          <p className="mt-2 text-center text-sm text-slate-500 font-medium">
            Shared expense management for modern teams & apartments
          </p>
        </div>

        {/* Error notification */}
        {errorMsg && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-4 flex items-start space-x-3 text-red-700 text-sm">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <p className="font-medium">{errorMsg}</p>
          </div>
        )}

        {/* Input Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4">
            <Input
              label="Username"
              id="username"
              type="text"
              autoComplete="username"
              placeholder="e.g. aisha"
              error={errors.username?.message}
              {...register('username')}
            />

            <Input
              label="Password"
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              error={errors.password?.message}
              {...register('password')}
            />
          </div>

          <div>
            <Button
              type="submit"
              variant="primary"
              className="w-full py-2.5 text-sm"
              isLoading={isSubmitting}
            >
              Sign In
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
export default Login;
