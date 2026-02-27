import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-slate-900 text-center px-4">
      <h1 className="text-9xl font-black text-slate-800">404</h1>
      <p className="text-2xl font-semibold text-slate-400 mt-4">Lost in the stream?</p>
      <Link 
        to="/" 
        className="mt-8 px-6 py-3 bg-blue-600 hover:bg-blue-500 transition-colors rounded-full font-bold shadow-lg"
      >
        Go Back Home
      </Link>
    </div>
  );
}