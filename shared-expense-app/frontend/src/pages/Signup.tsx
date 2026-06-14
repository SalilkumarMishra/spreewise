import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { ArrowRightLeft, AlertTriangle, UserPlus } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';

const signupSchema = z
  .object({
    full_name: z.string().min(2, 'Full name must be at least 2 characters'),
    username: z
      .string()
      .min(3, 'Username must be at least 3 characters')
      .max(30, 'Username cannot exceed 30 characters')
      .regex(/^[a-z0-9_]+$/, 'Username can only contain lowercase letters, numbers, and underscores'),
    email: z.string().email('Please enter a valid email address'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm_password: z.string().min(1, 'Please confirm your password'),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });

type SignupFormInput = z.infer<typeof signupSchema>;

const Signup: React.FC = () => {
  const { registerAction } = useAuth();
  const navigate = useNavigate();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormInput>({ resolver: zodResolver(signupSchema) });

  const onSubmit = async (data: SignupFormInput) => {
    setErrorMsg(null);
    try {
      await registerAction(
        data.full_name,
        data.username,
        data.email,
        data.password,
        data.confirm_password
      );
      navigate('/dashboard', { replace: true });
    } catch (e: any) {
      const detail = e.response?.data;
      if (detail && typeof detail === 'object') {
        // Extract first validation error from DRF response
        const firstError = Object.values(detail).flat()[0];
        setErrorMsg(typeof firstError === 'string' ? firstError : 'Registration failed. Please try again.');
      } else {
        setErrorMsg('Could not connect to the server. Make sure the backend is running.');
      }
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md space-y-8 bg-white p-8 border border-slate-200 rounded-2xl shadow-xl">
        {/* Branding */}
        <div className="flex flex-col items-center">
          <div className="bg-violet-600 p-3 rounded-2xl text-white shadow-lg shadow-violet-600/10">
            <ArrowRightLeft className="h-8 w-8" />
          </div>
          <h1 className="mt-6 text-center text-3xl font-extrabold tracking-tight text-slate-900">
            Create your account
          </h1>
          <p className="mt-2 text-center text-sm text-slate-500">
            Join Spreewise — split expenses effortlessly
          </p>
        </div>

        {/* Error */}
        {errorMsg && (
          <div className="rounded-lg bg-red-50 border border-red-200 p-4 flex items-start space-x-3 text-red-700 text-sm">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
            <p className="font-medium">{errorMsg}</p>
          </div>
        )}

        {/* Form */}
        <form className="mt-6 space-y-5" onSubmit={handleSubmit(onSubmit)}>
          <Input
            label="Full Name"
            id="full_name"
            type="text"
            placeholder="e.g. Aisha Patel"
            error={errors.full_name?.message}
            {...register('full_name')}
          />
          <Input
            label="Username"
            id="username"
            type="text"
            autoComplete="username"
            placeholder="e.g. aisha (lowercase, no spaces)"
            error={errors.username?.message}
            {...register('username')}
          />
          <Input
            label="Email"
            id="email"
            type="email"
            autoComplete="email"
            placeholder="e.g. aisha@example.com"
            error={errors.email?.message}
            {...register('email')}
          />
          <Input
            label="Password"
            id="password"
            type="password"
            autoComplete="new-password"
            placeholder="Min. 8 characters"
            error={errors.password?.message}
            {...register('password')}
          />
          <Input
            label="Confirm Password"
            id="confirm_password"
            type="password"
            autoComplete="new-password"
            placeholder="Re-enter your password"
            error={errors.confirm_password?.message}
            {...register('confirm_password')}
          />

          <Button
            type="submit"
            variant="primary"
            className="w-full py-2.5 text-sm"
            isLoading={isSubmitting}
          >
            <UserPlus className="h-4 w-4 mr-2 inline" />
            Create Account
          </Button>
        </form>

        {/* Links */}
        <div className="text-center space-y-2">
          <p className="text-sm text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="font-semibold text-violet-600 hover:text-violet-700 transition-colors">
              Sign in
            </Link>
          </p>
          <p className="text-sm text-slate-500">
            Have an invite code?{' '}
            <Link to="/join-group" className="font-semibold text-violet-600 hover:text-violet-700 transition-colors">
              Join a group
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Signup;
