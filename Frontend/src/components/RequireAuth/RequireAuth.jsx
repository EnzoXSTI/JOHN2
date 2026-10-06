import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/useAuth';

// ==========================================================
// GUARDA DE ROTAS
// ==========================================================
// Telas que exigem login passam por aqui no App.jsx. Sem
// usuário no contexto, redireciona para /login guardando a
// rota de origem para voltar após autenticar.

export default function RequireAuth({ children, tipos }) {
    const { usuario, logado } = useAuth();
    const location = useLocation();

    if (!logado) {
        return <Navigate to="/login" replace state={{ de: location.pathname + location.search }} />;
    }

    if (tipos && tipos.length > 0 && !tipos.includes(Number(usuario?.tipo))) {
        return <Navigate to="/" replace />;
    }

    return children;
}
