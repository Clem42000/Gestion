import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os
import hashlib

# Configuration de la page
st.set_page_config(
    page_title="Gestion Dépenses",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé
st.markdown("""
<style>
    .stMetric {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        font-weight: 600 !important;
    }
    
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 40px;
        background-color: var(--secondary-background-color);
        border-radius: 16px;
        border: 1px solid var(--border-color);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .info-box {
        background-color: rgba(59, 130, 246, 0.1);
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid #3b82f6;
        margin: 16px 0;
    }
    
    .warning-box {
        background-color: rgba(245, 158, 11, 0.1);
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid #f59e0b;
        margin: 16px 0;
    }
    
    .success-box {
        background-color: rgba(16, 185, 129, 0.1);
        padding: 16px;
        border-radius: 8px;
        border-left: 4px solid #10b981;
        margin: 16px 0;
    }
    
    .month-selector {
        position: sticky;
        top: 0;
        z-index: 999;
        background-color: var(--background-color);
        padding: 16px 0;
        border-bottom: 2px solid var(--border-color);
        margin-bottom: 24px;
    }
    
    h1, h2, h3 {
        font-weight: 600;
    }
    
    .streamlit-expanderHeader {
        background-color: var(--secondary-background-color);
        border-radius: 8px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Fichiers de sauvegarde
RULES_FILE = "categorization_rules.json"
TRANSACTIONS_FILE = "all_transactions.csv"

# ========================================
# AUTHENTIFICATION
# ========================================

def hash_password(password):
    """Hash un mot de passe avec SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password():
    """Système d'authentification"""
    
    # Hash du mot de passe (défaut: "password")
    # Pour changer: print(hashlib.sha256("VOTRE_MDP".encode()).hexdigest())
    STORED_PASSWORD_HASH = "73efb19f64603709eb977b600173843d3c779f7b971304bd28ca13142fbf6009"
    
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("<div class='login-container'>", unsafe_allow_html=True)
            
            st.markdown("### Gestionnaire de Finances")
            st.markdown("Accès sécurisé")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            password = st.text_input(
                "Mot de passe",
                type="password",
                key="password_input",
                label_visibility="collapsed",
                placeholder="Entrez votre mot de passe"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("Se connecter", type="primary", use_container_width=True):
                if password and hash_password(password) == STORED_PASSWORD_HASH:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Mot de passe incorrect")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.stop()

check_password()

# ========================================
# FONCTIONS UTILITAIRES
# ========================================

def load_rules():
    """Charge les règles de catégorisation"""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_rules():
    """Sauvegarde les règles"""
    with open(RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(st.session_state.rules, f, ensure_ascii=False, indent=2)

def load_transactions():
    """Charge toutes les transactions"""
    if os.path.exists(TRANSACTIONS_FILE):
        try:
            return pd.read_csv(TRANSACTIONS_FILE, sep=';')
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def save_transactions():
    """Sauvegarde les transactions"""
    st.session_state.all_transactions.to_csv(TRANSACTIONS_FILE, sep=';', index=False)

def categorize_transaction(row, rules):
    """Applique les règles de catégorisation"""
    if hasattr(row, 'get'):
        label = str(row.get('label', ''))
        category_parent = str(row.get('categoryParent', ''))
        category = str(row.get('category', ''))
    else:
        label = str(row)
        category_parent = ''
        category = ''
    
    label_lower = label.lower()
    category_parent_lower = category_parent.lower()
    category_lower = category.lower()
    
    # Détecter mouvements internes
    if 'mouvements internes' in category_parent_lower or 'mouvements internes' in category_lower:
        return 'Mouvement interne'
    
    if 'virements reçus de comptes à comptes' in category_lower or 'virements émis de comptes à comptes' in category_lower:
        return 'Mouvement interne'
    
    internal_keywords = [
        'virement depuis livret a',
        'vir virement depuis livret a',
        'virement depuis boursobank',
        'vir virement depuis boursobank'
    ]
    if any(keyword in label_lower for keyword in internal_keywords):
        return 'Mouvement interne'
    
    # Règles personnalisées
    for rule in rules:
        if rule['keyword'].lower() in label_lower:
            return rule['category']
    
    return 'Non catégorisé'

def parse_csv(uploaded_file):
    """Parse le CSV de Boursobank"""
    try:
        df = pd.read_csv(uploaded_file, sep=';', encoding='utf-8')
        
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].str.replace('"', '')
        
        if 'amount' in df.columns:
            df['amount'] = df['amount'].str.replace(' ', '').str.replace(',', '.').astype(float)
        
        df['autoCategory'] = df.apply(
            lambda row: categorize_transaction(row, st.session_state.rules), axis=1
        )
        
        return df
    except Exception as e:
        st.error(f"Erreur lors de la lecture du CSV : {e}")
        return None

def recategorize_all():
    """Recatégorise toutes les transactions"""
    if not st.session_state.all_transactions.empty:
        st.session_state.all_transactions['autoCategory'] = st.session_state.all_transactions.apply(
            lambda row: categorize_transaction(row, st.session_state.rules), axis=1
        )
        save_transactions()

def calculate_stats(df, selected_month=None):
    """Calcule les statistiques"""
    if df.empty:
        return {
            'total_expenses': 0,
            'total_income': 0,
            'balance': 0,
            'by_category': {},
            'savings_in': 0,
            'savings_out': 0,
            'net_savings': 0,
            'avg_daily_expense': 0,
            'largest_expense': {'label': '', 'amount': 0},
            'expense_count': 0
        }
    
    if selected_month and selected_month != "Tous les mois":
        df = df[df['dateOp'].str.startswith(selected_month)]
    
    # Mouvements internes
    internal = df[df['autoCategory'] == 'Mouvement interne']
    savings_in = abs(internal[internal['amount'] < 0]['amount'].sum())
    savings_out = internal[internal['amount'] > 0]['amount'].sum()
    net_savings = savings_in - savings_out
    
    # Revenus et dépenses (hors mouvements internes)
    df_filtered = df[df['autoCategory'] != 'Mouvement interne']
    
    expenses = df_filtered[df_filtered['amount'] < 0].copy()
    income = df_filtered[df_filtered['amount'] > 0].copy()
    
    total_expenses = abs(expenses['amount'].sum())
    total_income = income['amount'].sum()
    
    # Par catégorie
    expenses['category_final'] = expenses['autoCategory'].fillna(expenses['category'])
    by_category = expenses.groupby('category_final')['amount'].sum().abs().to_dict()
    
    # Statistiques supplémentaires
    expense_count = len(expenses)
    
    # Dépense moyenne par jour
    if not expenses.empty and selected_month and selected_month != "Tous les mois":
        days_in_month = pd.to_datetime(expenses['dateOp']).dt.day.max()
        avg_daily_expense = total_expenses / days_in_month if days_in_month > 0 else 0
    else:
        avg_daily_expense = 0
    
    # Plus grosse dépense
    if not expenses.empty:
        largest_idx = expenses['amount'].abs().idxmax()
        largest_expense = {
            'label': expenses.loc[largest_idx, 'label'],
            'amount': abs(expenses.loc[largest_idx, 'amount'])
        }
    else:
        largest_expense = {'label': '', 'amount': 0}
    
    return {
        'total_expenses': total_expenses,
        'total_income': total_income,
        'balance': total_income - total_expenses,
        'by_category': by_category,
        'savings_in': savings_in,
        'savings_out': savings_out,
        'net_savings': net_savings,
        'avg_daily_expense': avg_daily_expense,
        'largest_expense': largest_expense,
        'expense_count': expense_count
    }

def get_month_comparison(df):
    """Compare les statistiques entre mois"""
    if df.empty:
        return pd.DataFrame()
    
    df['month'] = df['dateOp'].str[:7]
    
    monthly_stats = []
    for month in sorted(df['month'].unique()):
        stats = calculate_stats(df, month)
        monthly_stats.append({
            'Mois': datetime.strptime(month, "%Y-%m").strftime("%B %Y"),
            'month_code': month,
            'Revenus': stats['total_income'],
            'Dépenses': stats['total_expenses'],
            'Solde': stats['balance'],
            'Épargne': stats['net_savings']
        })
    
    return pd.DataFrame(monthly_stats)

def export_to_excel():
    """Exporte vers Excel"""
    if st.session_state.all_transactions.empty:
        return None
    
    output_file = "export_finances.xlsx"
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        st.session_state.all_transactions.to_excel(writer, sheet_name='Transactions', index=False)
        
        rules_df = pd.DataFrame(st.session_state.rules)
        if not rules_df.empty:
            rules_df.to_excel(writer, sheet_name='Règles', index=False)
        
        monthly = get_month_comparison(st.session_state.all_transactions)
        if not monthly.empty:
            monthly.to_excel(writer, sheet_name='Comparaison mensuelle', index=False)
    
    return output_file

def get_budget_alerts(stats, budgets):
    """Génère des alertes de budget"""
    alerts = []
    for category, limit in budgets.items():
        if category in stats['by_category']:
            spent = stats['by_category'][category]
            percentage = (spent / limit) * 100
            if percentage >= 100:
                alerts.append({
                    'category': category,
                    'spent': spent,
                    'limit': limit,
                    'status': 'danger',
                    'message': f"Budget dépassé de {spent - limit:.2f} €"
                })
            elif percentage >= 80:
                alerts.append({
                    'category': category,
                    'spent': spent,
                    'limit': limit,
                    'status': 'warning',
                    'message': f"{percentage:.0f}% du budget utilisé"
                })
    return alerts

# ========================================
# INITIALISATION
# ========================================

if 'rules' not in st.session_state:
    st.session_state.rules = load_rules()
if 'all_transactions' not in st.session_state:
    st.session_state.all_transactions = load_transactions()
if 'budgets' not in st.session_state:
    st.session_state.budgets = {}
if 'selected_month' not in st.session_state:
    st.session_state.selected_month = "Tous les mois"

# ========================================
# HEADER & NAVIGATION
# ========================================

# Titre principal
st.title("Gestionnaire de Finances")

# Sélecteur de mois en haut (sticky)
if not st.session_state.all_transactions.empty:
    st.markdown("<div class='month-selector'>", unsafe_allow_html=True)
    
    available_months = sorted(
        st.session_state.all_transactions['dateOp'].str[:7].unique(),
        reverse=True
    )
    
    col1, col2, col3 = st.columns([2, 3, 2])
    with col2:
        selected_month = st.selectbox(
            "Période",
            ["Tous les mois"] + list(available_months),
            format_func=lambda x: x if x == "Tous les mois" else datetime.strptime(x, "%Y-%m").strftime("%B %Y"),
            key="month_selector",
            label_visibility="collapsed"
        )
        st.session_state.selected_month = selected_month
    
    st.markdown("</div>", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("## Navigation")
    page = st.radio(
        "",
        ["Tableau de bord", "Évolution", "Transactions", "Catégories", "Budgets", "Import CSV"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    if not st.session_state.all_transactions.empty:
        st.markdown("## Statistiques globales")
        total_trans = len(st.session_state.all_transactions)
        total_rules = len(st.session_state.rules)
        months = st.session_state.all_transactions['dateOp'].str[:7].nunique()
        
        st.metric("Transactions", total_trans)
        st.metric("Règles actives", total_rules)
        st.metric("Mois", months)
        
        st.markdown("---")
        
        if st.button("Exporter Excel", use_container_width=True):
            excel_file = export_to_excel()
            if excel_file:
                with open(excel_file, 'rb') as f:
                    st.download_button(
                        "Télécharger",
                        f,
                        file_name=excel_file,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
    
    st.markdown("---")
    if st.button("Déconnexion", type="secondary", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# ========================================
# PAGE: TABLEAU DE BORD
# ========================================
if page == "Tableau de bord":
    
    if st.session_state.all_transactions.empty:
        st.info("Aucune transaction chargée. Importez un fichier CSV pour commencer.")
    else:
        df = st.session_state.all_transactions
        stats = calculate_stats(df, st.session_state.selected_month if st.session_state.selected_month != "Tous les mois" else None)
        
        # Indicateurs clés
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Revenus", f"{stats['total_income']:.2f} €")
        
        with col2:
            st.metric(
                "Dépenses",
                f"{stats['total_expenses']:.2f} €",
                delta=f"-{stats['total_expenses']:.2f} €",
                delta_color="inverse"
            )
        
        with col3:
            balance = stats['balance']
            st.metric(
                "Solde",
                f"{balance:.2f} €",
                delta=f"{balance:.2f} €",
                delta_color="normal" if balance >= 0 else "inverse"
            )
        
        with col4:
            st.metric(
                "Épargne",
                f"{stats['net_savings']:.2f} €",
                delta=f"{stats['net_savings']:.2f} €",
                delta_color="normal" if stats['net_savings'] >= 0 else "inverse"
            )
        
        # Statistiques secondaires
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if stats['avg_daily_expense'] > 0:
                st.metric("Dépense moyenne / jour", f"{stats['avg_daily_expense']:.2f} €")
            else:
                st.metric("Nombre de dépenses", stats['expense_count'])
        
        with col2:
            if stats['total_income'] > 0:
                savings_rate = (stats['net_savings'] / stats['total_income'] * 100)
                st.metric("Taux d'épargne", f"{savings_rate:.1f}%")
            else:
                st.metric("Taux d'épargne", "0%")
        
        with col3:
            if stats['largest_expense']['amount'] > 0:
                st.metric("Plus grosse dépense", f"{stats['largest_expense']['amount']:.2f} €")
        
        # Alertes budgets
        if st.session_state.budgets:
            alerts = get_budget_alerts(stats, st.session_state.budgets)
            if alerts:
                st.markdown("---")
                st.markdown("### Alertes budget")
                for alert in alerts:
                    if alert['status'] == 'danger':
                        st.markdown(f"""
                        <div class="warning-box">
                            <strong>{alert['category']}</strong> : {alert['message']}
                        </div>
                        """, unsafe_allow_html=True)
                    elif alert['status'] == 'warning':
                        st.markdown(f"""
                        <div class="info-box">
                            <strong>{alert['category']}</strong> : {alert['message']}
                        </div>
                        """, unsafe_allow_html=True)
        
        # Graphiques
        if stats['by_category']:
            st.markdown("---")
            st.markdown("### Répartition des dépenses")
            
            col1, col2 = st.columns(2)
            
            with col1:
                cat_df = pd.DataFrame(list(stats['by_category'].items()), columns=['Catégorie', 'Montant'])
                cat_df = cat_df.sort_values('Montant', ascending=False).head(10)
                
                fig_bar = px.bar(
                    cat_df,
                    y='Catégorie',
                    x='Montant',
                    orientation='h',
                    color='Montant',
                    color_continuous_scale='Reds'
                )
                fig_bar.update_layout(
                    showlegend=False,
                    height=400,
                    xaxis_title="Montant (€)",
                    yaxis_title="",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=0, r=0, t=0, b=0)
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col2:
                fig_pie = px.pie(
                    cat_df,
                    values='Montant',
                    names='Catégorie',
                    hole=0.5
                )
                fig_pie.update_layout(
                    height=400,
                    showlegend=True,
                    paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=0, r=0, t=0, b=0)
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # Tableau détaillé
            st.markdown("### Détails par catégorie")
            cat_df_full = pd.DataFrame(list(stats['by_category'].items()), columns=['Catégorie', 'Montant'])
            cat_df_full = cat_df_full.sort_values('Montant', ascending=False)
            cat_df_full['Pourcentage'] = (cat_df_full['Montant'] / cat_df_full['Montant'].sum() * 100).round(1)
            
            # Ajouter le budget si défini
            if st.session_state.budgets:
                cat_df_full['Budget'] = cat_df_full['Catégorie'].map(st.session_state.budgets)
                cat_df_full['Reste'] = cat_df_full.apply(
                    lambda row: row['Budget'] - row['Montant'] if pd.notna(row['Budget']) else None,
                    axis=1
                )
            
            cat_df_full['Montant'] = cat_df_full['Montant'].apply(lambda x: f"{x:.2f} €")
            cat_df_full['Pourcentage'] = cat_df_full['Pourcentage'].apply(lambda x: f"{x}%")
            
            display_cols = ['Catégorie', 'Montant', 'Pourcentage']
            if 'Budget' in cat_df_full.columns:
                cat_df_full['Budget'] = cat_df_full['Budget'].apply(lambda x: f"{x:.2f} €" if pd.notna(x) else "-")
                cat_df_full['Reste'] = cat_df_full['Reste'].apply(lambda x: f"{x:.2f} €" if pd.notna(x) else "-")
                display_cols.extend(['Budget', 'Reste'])
            
            st.dataframe(cat_df_full[display_cols], use_container_width=True, hide_index=True)

# ========================================
# PAGE: ÉVOLUTION
# ========================================
elif page == "Évolution":
    st.header("Évolution mensuelle")
    
    if st.session_state.all_transactions.empty:
        st.info("Aucune transaction chargée.")
    else:
        monthly_data = get_month_comparison(st.session_state.all_transactions)
        
        if not monthly_data.empty:
            # Graphique d'évolution
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=monthly_data['Mois'],
                y=monthly_data['Revenus'],
                mode='lines+markers',
                name='Revenus',
                line=dict(color='#10b981', width=3),
                marker=dict(size=8)
            ))
            
            fig.add_trace(go.Scatter(
                x=monthly_data['Mois'],
                y=monthly_data['Dépenses'],
                mode='lines+markers',
                name='Dépenses',
                line=dict(color='#ef4444', width=3),
                marker=dict(size=8)
            ))
            
            fig.add_trace(go.Scatter(
                x=monthly_data['Mois'],
                y=monthly_data['Épargne'],
                mode='lines+markers',
                name='Épargne',
                line=dict(color='#3b82f6', width=3),
                marker=dict(size=8)
            ))
            
            fig.update_layout(
                height=500,
                hovermode='x unified',
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                xaxis_title="",
                yaxis_title="Montant (€)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Tableau comparatif
            st.markdown("### Tableau comparatif")
            display_monthly = monthly_data.copy()
            for col in ['Revenus', 'Dépenses', 'Solde', 'Épargne']:
                display_monthly[col] = display_monthly[col].apply(lambda x: f"{x:.2f} €")
            
            st.dataframe(
                display_monthly[['Mois', 'Revenus', 'Dépenses', 'Solde', 'Épargne']],
                use_container_width=True,
                hide_index=True
            )

# ========================================
# PAGE: TRANSACTIONS
# ========================================
elif page == "Transactions":
    st.header("Liste des transactions")
    
    if st.session_state.all_transactions.empty:
        st.info("Aucune transaction chargée.")
    else:
        df = st.session_state.all_transactions.copy()
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            categories = ["Toutes"] + sorted(df['autoCategory'].unique().tolist())
            selected_category = st.selectbox("Catégorie", categories)
        
        with col2:
            type_filter = st.selectbox("Type", ["Tous", "Dépenses", "Revenus", "Mouvements internes"])
        
        with col3:
            search = st.text_input("Rechercher", placeholder="Libellé...")
        
        # Appliquer filtres
        filtered_df = df.copy()
        
        if st.session_state.selected_month != "Tous les mois":
            filtered_df = filtered_df[filtered_df['dateOp'].str.startswith(st.session_state.selected_month)]
        
        if selected_category != "Toutes":
            filtered_df = filtered_df[filtered_df['autoCategory'] == selected_category]
        
        if type_filter == "Dépenses":
            filtered_df = filtered_df[filtered_df['amount'] < 0]
        elif type_filter == "Revenus":
            filtered_df = filtered_df[filtered_df['amount'] > 0]
        elif type_filter == "Mouvements internes":
            filtered_df = filtered_df[filtered_df['autoCategory'] == 'Mouvement interne']
        
        if search:
            filtered_df = filtered_df[filtered_df['label'].str.contains(search, case=False, na=False)]
        
        # Statistiques
        st.markdown(f"### {len(filtered_df)} transactions")
        
        if not filtered_df.empty:
            col1, col2, col3 = st.columns(3)
            with col1:
                total_in = filtered_df[filtered_df['amount'] > 0]['amount'].sum()
                st.metric("Entrées", f"{total_in:.2f} €")
            with col2:
                total_out = abs(filtered_df[filtered_df['amount'] < 0]['amount'].sum())
                st.metric("Sorties", f"{total_out:.2f} €")
            with col3:
                st.metric("Solde", f"{total_in - total_out:.2f} €")
            
            st.markdown("---")
            
            # Tableau
            display_df = filtered_df[['dateOp', 'label', 'autoCategory', 'amount']].sort_values('dateOp', ascending=False)
            display_df.columns = ['Date', 'Libellé', 'Catégorie', 'Montant']
            display_df['Montant'] = display_df['Montant'].apply(lambda x: f"{x:.2f} €")
            
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)
        else:
            st.info("Aucune transaction ne correspond aux filtres")

# ========================================
# PAGE: CATÉGORIES (RÈGLES)
# ========================================
elif page == "Catégories":
    st.header("Règles de catégorisation")
    
    st.markdown("""
    <div class="info-box">
        Les règles permettent de catégoriser automatiquement vos transactions.
        Si le libellé contient le mot-clé, la transaction sera classée dans la catégorie définie.
    </div>
    """, unsafe_allow_html=True)
    
    # Formulaire d'ajout
    col1, col2, col3 = st
