import firebirdsql

con = firebirdsql.connect(
    host='localhost',
    database=r'C:\Users\mathe\Documents\Salvar\Backend\CORTAE.FDB',
    user='SYSDBA',
    password='masterkey',
    charset='UTF8'
)
cur = con.cursor()

# Ver categorias dos cortes
print("=== CATEGORIAS DOS CORTES ===")
cur.execute("SELECT CATEGORIA, COUNT(*) FROM CORTE_VISAGISMO GROUP BY CATEGORIA ORDER BY CATEGORIA")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]}")

con.close()
