import { Routes, Route } from 'react-router-dom';

import Header from './components/Header/header';
import Footer from './components/Footer/footer';
import RequireAuth from './components/RequireAuth/RequireAuth';
import { AuthProvider } from './contexts/AuthContext';

import Home from './pages/Home/Home';
import Login from './pages/Login/login';
import Cadastro from './pages/Cadastro/cadastro';
import RedefinirSenha from './pages/RedefinacaoSenha/RedefinacaoSenha';
import EditarUsuario from './pages/EditarUsuario/EditarUsuario';
import VerificarCodigo from './pages/VerificarCodigo/VerificarCodigo';
import Estabelecimento from './pages/Estabelecimento/Estabelecimento';
import CadastroBarbearia from './pages/CadastroBarbearia/CadastroBarbearia.jsx';
import BarbeariasDisponiveis from './pages/BarbeariasDisponiveis/BarbeariasDisponiveis';
import Erro from "./pages/Erro/Erro";
import PersonalizacaoBarbearia from "./pages/PersonalizacaoBarbearia/PersonalizacaoBarbearia.jsx";
import EditarBarbearia from "./pages/EditarBarbearia/EditarBarbearia.jsx";
import AdminUsuarios from "./pages/AdminUsuarios/AdminUsuarios.jsx";
import AdminCortes from "./pages/AdminCortes/AdminCortes.jsx";
import Visagismo from "./pages/Visagismo/Visagismo.jsx";
import Agendamento from "./pages/Agendamento/Agendamento.jsx";
import AdminFinanceiro from "./pages/AdminFinanceiro/AdminFinanceiro.jsx";
import SelecionarServicos from "./pages/SelecionarServicos/SelecionarServicos.jsx";
import MeusAgendamentos from "./pages/MeusAgendamentos/MeusAgendamentos.jsx";
import AgendamentosAdm from "./pages/agendamentosadm/agendamentosadm.jsx";

export default function App() {
    return (
        <AuthProvider>
            <Header />

            <Routes>
                <Route
                    path="/*"
                    element={<Erro />}
                />
                <Route
                    path="/"
                    element={<Home />}
                />

                <Route
                    path="/login"
                    element={<Login />}
                />

                <Route
                    path="/cadastro"
                    element={<Cadastro />}
                />

                <Route
                    path="/redefinirsenha"
                    element={<RedefinirSenha />}
                />

                <Route
                    path="/editarusuario"
                    element={<RequireAuth><EditarUsuario /></RequireAuth>}
                />

                <Route
                    path="/verificar-codigo"
                    element={<VerificarCodigo />}
                />

                <Route
                    path="/estabelecimento"
                    element={<Estabelecimento />}
                />

                <Route
                    path="/barbearias-disponiveis"
                    element={<BarbeariasDisponiveis />}
                />

                <Route
                    path="/cadastrobarbearia"
                    element={<CadastroBarbearia />}
                />

                <Route
                    path="/personalizacaobarbearia"
                    element={<RequireAuth tipos={[0, 2]}><PersonalizacaoBarbearia /></RequireAuth>}
                />

                <Route
                    path="/editarbarbearia"
                    element={<RequireAuth tipos={[0, 2]}><EditarBarbearia /></RequireAuth>}
                />

                <Route path="/visagismo" element={<RequireAuth><Visagismo /></RequireAuth>} />

                <Route path="/selecionar-servicos" element={<SelecionarServicos />} />

                <Route path="/agendamento" element={<RequireAuth><Agendamento /></RequireAuth>} />

                <Route path="/meus-agendamentos" element={<RequireAuth><MeusAgendamentos /></RequireAuth>} />

                <Route path="/agendamentosadm" element={<RequireAuth tipos={[0, 2]}><AgendamentosAdm /></RequireAuth>} />

                <Route path="/financeiro" element={<RequireAuth tipos={[0, 2]}><AdminFinanceiro /></RequireAuth>} />

                <Route path="/admin/usuarios" element={<RequireAuth tipos={[0]}><AdminUsuarios /></RequireAuth>} />
                <Route path="/admin/cortes" element={<RequireAuth tipos={[0, 2]}><AdminCortes /></RequireAuth>} />
                <Route path="/editarusuario/:id" element={<RequireAuth><EditarUsuario /></RequireAuth>} />


            </Routes>

            <Footer />
        </AuthProvider>
    );
}
