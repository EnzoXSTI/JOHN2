import { useContext } from 'react';
import { AuthContext } from './contextoAutenticacao';

export function useAuth() {
    return useContext(AuthContext);
}
