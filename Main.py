import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import os

# Configuration de la page
st.set_page_config(
    page_title="Gestion Dépenses Boursobank",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour un design moderne compatible mode sombre
st.markdown("""
<style>
    /* Métriques avec bon contraste */
    .stMetric {
        background-color: var(--secondary-background-color);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid var(--border-color);
    }
    
    /* Amélioration des cartes métriques */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 600 !important;
    }
    
    /* Boîtes de messages - utiliser les variables Streamlit */
    .success-box {
        background-color: rgba(16, 185, 129, 0.1);
        color: var(--text-color);
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #10b981;
        margin: 10px 0;
    }
    .warning-box {
        background-color: rgba(245, 158, 11, 0.1);
        color: var(--text-color);
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #f59e0b;
        margin: 10px 0;
    }
    .info-box {
        background-color: rgba(59, 130, 246, 0.1);
        color: var(--text-color);
        padding: 15px;
        border-radius: 10px;
        border-left: 4px solid #3b82f6;
        margin: 10px 0;
    }
    
    /* Graphiques */
    .js-plotly-plot {
        border-radius: 10px;
    }
    
    /* Expanders */
    .streamlit-expanderHeader {
        background-color: var(--secondary-background-color);
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Fichiers de sauvegarde
RULES_FILE = "categorization_rules.json"
TRANSACTIONS_FILE = "all_transactions.csv"

# ========================================
# FONCTIONS UTILITAIRES
# ========================================

def load_rules():
    """Charge les règles de catégorisation depuis le fichier JSON"""
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_rules():
    """Sauvegarde les règles de catégorisation"""
    with open(RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(st.session_state.rules, f, ensure_ascii=False, indent=2)

def load_transactions():
    """Charge toutes les transactions depuis le fichier CSV"""
    if os.path.exists(TRANSACTIONS_FILE):
        try:
            return pd.read_csv(TRANSACTIONS_FILE, sep=';')
        except:
            return pd.DataFrame()
    return pd.DataFrame()

def save_transactions():
    """Sauvegarde toutes les transactions"""
    st.session_state.all_transactions.to_csv(TRANSACTIONS_FILE, sep=';', index=False)

def categorize_transaction(row, rules):
    """Applique les règles de catégorisation à une transaction"""
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
    
    # Détecter les mouvements internes
    if 'mouvements internes' in category_parent_lower or 'mouvements internes' in category_lower:
        return '💰 Mouvement interne'
    
    if 'virements reçus de comptes à comptes' in category_lower or 'virements émis de comptes à comptes' in category_lower:
        return '💰 Mouvement interne'
    
    internal_keywords = [
        'virement depuis livret a',
        'vir virement depuis livret a',
        'virement depuis boursobank',
        'vir virement depuis boursobank'
    ]
    if any(keyword in label_lower for keyword in internal_keywords):
        return '💰 Mouvement interne'
    
    # Appliquer les règles personnalisées
    for rule in rules:
        if rule['keyword'].lower() in label_lower:
            return rule['category']
    
    return 'Non catégorisé'

def parse_csv(uploaded_file):
    """Parse le fichier CSV de Boursobank"""
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
        st.error(f"❌ Erreur lors de la lecture du CSV : {e}")
        return None

def recategorize_all():
    """Recatégorise toutes les transactions avec les règles actuelles"""
    if not st.session_state.all_transactions.empty:
        st.session_state.all_transactions['autoCategory'] = st.session_state.all_transactions.apply(
            lambda row: categorize_transaction(row, st.session_state.rules), axis=1
        )
        save_transactions()

def calculate_stats(df, selected_month=None):
    """Calcule les statistiques pour le mois sélectionné"""
    if df.empty:
        return {
            'total_expenses': 0,
            'total_income': 0,
            'balance': 0,
            'by_category': {},
            'savings_in': 0,
            'savings_out': 0,
            'net_savings': 0
        }
    
    if selected_month and selected_month != "Tous les mois":
        df = df[df['dateOp'].str.startswith(selected_month)]
    
    internal = df[df['autoCategory'] == '💰 Mouvement interne']
    savings_in = abs(internal[internal['amount'] < 0]['amount'].sum())
    savings_out = internal[internal['amount'] > 0]['amount'].sum()
    net_savings = savings_in - savings_out
    
    df_filtered = df[df['autoCategory'] != '💰 Mouvement interne']
    
    expenses = df_filtered[df_filtered['amount'] < 0].copy()
    income = df_filtered[df_filtered['amount'] > 0].copy()
    
    total_expenses = abs(expenses['amount'].sum())
    total_income = income['amount'].sum()
    
    expenses['category_final'] = expenses['autoCategory'].fillna(expenses['category'])
    by_category = expenses.groupby('category_final')['amount'].sum().abs().to_dict()
    
    return {
        'total_expenses': total_expenses,
        'total_income': total_income,
        'balance': total_income - total_expenses,
        'by_category': by_category,
        'savings_in': savings_in,
        'savings_out': savings_out,
        'net_savings': net_savings
    }

def get_month_comparison(df):
    """Compare les statistiques entre les mois"""
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
    """Exporte les données vers Excel"""
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

# ========================================
# INITIALISATION DU SESSION STATE
# ========================================

if 'rules' not in st.session_state:
    st.session_state.rules = load_rules()
if 'all_transactions' not in st.session_state:
    st.session_state.all_transactions = load_transactions()
if 'show_debug' not in st.session_state:
    st.session_state.show_debug = False

# ========================================
# INTERFACE UTILISATEUR
# ========================================

# Header avec logo et titre
col1, col2 = st.columns([1, 5])
with col1:
    st.markdown("# 💰")
with col2:
    st.title("Gestionnaire de Dépenses Boursobank")
    st.caption("Suivez vos finances personnelles mois par mois")

st.markdown("---")

# Sidebar
with st.sidebar:
    st.markdown("## 📍 Navigation")
    page = st.radio(
        "",
        ["📊 Tableau de bord", "📈 Évolution", "📤 Import CSV", "⚙️ Règles", "📋 Transactions"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    st.markdown("## 📈 Statistiques")
    if not st.session_state.all_transactions.empty:
        total_trans = len(st.session_state.all_transactions)
        total_rules = len(st.session_state.rules)
        
        st.metric("📝 Transactions", total_trans)
        st.metric("⚙️ Règles actives", total_rules)
        
        months = st.session_state.all_transactions['dateOp'].str[:7].nunique()
        st.metric("📅 Mois enregistrés", months)
    else:
        st.info("💡 Importez vos transactions pour commencer")
    
    st.markdown("---")
    
    # Export Excel
    if not st.session_state.all_transactions.empty:
        if st.button("📥 Exporter vers Excel", use_container_width=True):
            excel_file = export_to_excel()
            if excel_file:
                with open(excel_file, 'rb') as f:
                    st.download_button(
                        "⬇️ Télécharger Excel",
                        f,
                        file_name=excel_file,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
    
    st.markdown("---")
    st.markdown("### 🔧 Options")
    st.session_state.show_debug = st.checkbox("Mode debug", value=st.session_state.show_debug)

# ========================================
# PAGE: TABLEAU DE BORD
# ========================================
if page == "📊 Tableau de bord":
    st.header("📊 Tableau de bord financier")
    
    if st.session_state.all_transactions.empty:
        st.warning("⚠️ Aucune transaction chargée. Importez un fichier CSV pour commencer.")
        st.info("👉 Rendez-vous dans la section **📤 Import CSV** pour importer vos données.")
    else:
        df = st.session_state.all_transactions
        
        # Sélection du mois
        available_months = sorted(df['dateOp'].str[:7].unique(), reverse=True)
        
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            selected_month = st.selectbox(
                "📅 Période",
                ["Tous les mois"] + list(available_months),
                format_func=lambda x: x if x == "Tous les mois" else datetime.strptime(x, "%Y-%m").strftime("%B %Y")
            )
        
        stats = calculate_stats(df, selected_month if selected_month != "Tous les mois" else None)
        
        # Cartes de statistiques principales
        st.markdown("### 💵 Vue d'ensemble")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "💰 Revenus",
                f"{stats['total_income']:.2f} €",
                help="Total des revenus (hors mouvements internes)"
            )
        
        with col2:
            st.metric(
                "💸 Dépenses",
                f"{stats['total_expenses']:.2f} €",
                delta=f"-{stats['total_expenses']:.2f} €" if stats['total_expenses'] > 0 else None,
                delta_color="inverse",
                help="Total des dépenses (hors mouvements internes)"
            )
        
        with col3:
            balance = stats['balance']
            st.metric(
                "💵 Solde",
                f"{balance:.2f} €",
                delta=f"{balance:.2f} €",
                delta_color="normal" if balance >= 0 else "inverse",
                help="Revenus - Dépenses"
            )
        
        with col4:
            net_savings = stats['net_savings']
            st.metric(
                "🏦 Épargne",
                f"{net_savings:.2f} €",
                delta=f"{net_savings:.2f} €",
                delta_color="normal" if net_savings >= 0 else "inverse",
                help="Évolution nette de votre épargne"
            )
        
        # Détails épargne
        if stats['savings_in'] > 0 or stats['savings_out'] > 0:
            st.markdown("---")
            st.markdown("### 💰 Détails des mouvements d'épargne")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "➡️ Versé sur livret A",
                    f"{stats['savings_in']:.2f} €",
                    help="Montant transféré vers votre épargne"
                )
            
            with col2:
                st.metric(
                    "⬅️ Retiré du livret A",
                    f"{stats['savings_out']:.2f} €",
                    help="Montant retiré de votre épargne"
                )
            
            with col3:
                savings_rate = (net_savings / stats['total_income'] * 100) if stats['total_income'] > 0 else 0
                st.metric(
                    "📊 Taux d'épargne",
                    f"{savings_rate:.1f}%",
                    help="Pourcentage de vos revenus épargnés"
                )
        
        st.markdown("---")
        
        # Graphiques
        if stats['by_category']:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📊 Dépenses par catégorie")
                cat_df = pd.DataFrame(list(stats['by_category'].items()), columns=['Catégorie', 'Montant'])
                cat_df = cat_df.sort_values('Montant', ascending=False).head(10)
                
                fig_bar = px.bar(
                    cat_df,
                    x='Montant',
                    y='Catégorie',
                    orientation='h',
                    color='Montant',
                    color_continuous_scale='Reds',
                    text='Montant'
                )
                fig_bar.update_traces(texttemplate='%{text:.2f}€', textposition='outside')
                fig_bar.update_layout(
                    showlegend=False,
                    height=400,
                    xaxis_title="Montant (€)",
                    yaxis_title="",
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col2:
                st.markdown("### 🥧 Répartition")
                fig_pie = px.pie(
                    cat_df,
                    values='Montant',
                    names='Catégorie',
                    hole=0.4,
                    color_discrete_sequence=px.colors.sequential.RdBu
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(
                    height=400,
                    showlegend=False,
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            # Tableau détaillé
            st.markdown("### 📋 Détails par catégorie")
            cat_df_full = pd.DataFrame(list(stats['by_category'].items()), columns=['Catégorie', 'Montant'])
            cat_df_full = cat_df_full.sort_values('Montant', ascending=False)
            cat_df_full['Pourcentage'] = (cat_df_full['Montant'] / cat_df_full['Montant'].sum() * 100).round(1)
            cat_df_full['Montant formaté'] = cat_df_full['Montant'].apply(lambda x: f"{x:.2f} €")
            cat_df_full['Pourcentage formaté'] = cat_df_full['Pourcentage'].apply(lambda x: f"{x}%")
            
            st.dataframe(
                cat_df_full[['Catégorie', 'Montant formaté', 'Pourcentage formaté']].rename(columns={
                    'Montant formaté': 'Montant',
                    'Pourcentage formaté': 'Pourcentage'
                }),
                use_container_width=True,
                hide_index=True
            )
        
        # Mode debug
        if st.session_state.show_debug:
            st.markdown("---")
            st.markdown("### 🔍 Mode Debug")
            
            internal_trans = df[df['autoCategory'] == '💰 Mouvement interne']
            
            if selected_month != "Tous les mois":
                internal_trans = internal_trans[internal_trans['dateOp'].str.startswith(selected_month)]
            
            if not internal_trans.empty:
                st.success(f"✅ {len(internal_trans)} mouvements internes détectés")
                with st.expander("Voir les détails"):
                    debug_df = internal_trans[['dateOp', 'label', 'categoryParent', 'category', 'amount']].copy()
                    st.dataframe(debug_df, use_container_width=True)
            else:
                st.warning("⚠️ Aucun mouvement interne détecté pour cette période")

# ========================================
# PAGE: ÉVOLUTION
# ========================================
elif page == "📈 Évolution":
    st.header("📈 Évolution mensuelle")
    
    if st.session_state.all_transactions.empty:
        st.warning("⚠️ Aucune transaction chargée.")
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
                title="Évolution des finances",
                xaxis_title="Mois",
                yaxis_title="Montant (€)",
                height=500,
                hovermode='x unified',
                plot_bgcolor='white',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Tableau comparatif
            st.markdown("### 📊 Tableau comparatif")
            display_monthly = monthly_data.copy()
            for col in ['Revenus', 'Dépenses', 'Solde', 'Épargne']:
                display_monthly[col] = display_monthly[col].apply(lambda x: f"{x:.2f} €")
            
            st.dataframe(
                display_monthly[['Mois', 'Revenus', 'Dépenses', 'Solde', 'Épargne']],
                use_container_width=True,
                hide_index=True
            )

# ========================================
# PAGE: IMPORT CSV
# ========================================
elif page == "📤 Import CSV":
    st.header("📤 Importer vos transactions")
    
    st.markdown("""
    <div class="info-box">
        <h4>📝 Instructions</h4>
        <ol>
            <li>Connectez-vous à votre compte Boursobank</li>
            <li>Exportez vos transactions au format CSV</li>
            <li>Sélectionnez le fichier ci-dessous</li>
            <li>Les transactions seront automatiquement catégorisées</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader(
        "Choisissez votre fichier CSV",
        type=['csv'],
        help="Format attendu : export CSV de Boursobank"
    )
    
    if uploaded_file is not None:
        new_df = parse_csv(uploaded_file)
        
        if new_df is not None:
            st.markdown(f"""
            <div class="success-box">
                ✅ <strong>{len(new_df)} transactions</strong> trouvées dans le fichier
            </div>
            """, unsafe_allow_html=True)
            
            # Aperçu
            st.markdown("### 👀 Aperçu des données")
            preview_df = new_df[['dateOp', 'label', 'autoCategory', 'amount']].head(10)
            preview_df.columns = ['Date', 'Libellé', 'Catégorie', 'Montant']
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
            
            # Statistiques de l'import
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Transactions", len(new_df))
            with col2:
                uncategorized = len(new_df[new_df['autoCategory'] == 'Non catégorisé'])
                st.metric("Non catégorisées", uncategorized)
            with col3:
                internal = len(new_df[new_df['autoCategory'] == '💰 Mouvement interne'])
                st.metric("Mouvements internes", internal)
            
            # Bouton d'import
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("✅ Confirmer l'import", type="primary", use_container_width=True):
                    if st.session_state.all_transactions.empty:
                        st.session_state.all_transactions = new_df
                    else:
                        st.session_state.all_transactions = pd.concat(
                            [st.session_state.all_transactions, new_df],
                            ignore_index=True
                        )
                        st.session_state.all_transactions.drop_duplicates(
                            subset=['dateOp', 'label', 'amount'],
                            inplace=True
                        )
                    
                    save_transactions()
                    st.success(f"✅ {len(new_df)} transactions importées avec succès !")
                    st.balloons()
                    st.rerun()

# ========================================
# PAGE: RÈGLES
# ========================================
elif page == "⚙️ Règles":
    st.header("⚙️ Règles de catégorisation")
    
    st.markdown("""
    <div class="info-box">
        Les règles permettent de catégoriser automatiquement vos transactions.
        Si le libellé contient le mot-clé, la transaction sera classée dans la catégorie définie.
    </div>
    """, unsafe_allow_html=True)
    
    # Formulaire d'ajout
    st.markdown("### ➕ Ajouter une nouvelle règle")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        new_keyword = st.text_input(
            "Mot-clé",
            placeholder="Ex: colruyt, carrefour, shell",
            help="Le mot-clé sera recherché dans le libellé (insensible à la casse)"
        )
    
    with col2:
        new_category = st.text_input(
            "Catégorie",
            placeholder="Ex: Alimentation, Transport, Loisirs",
            help="La catégorie à attribuer automatiquement"
        )
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Ajouter", type="primary", use_container_width=True):
            if new_keyword and new_category:
                # Vérifier si la règle existe déjà
                exists = any(r['keyword'].lower() == new_keyword.lower() for r in st.session_state.rules)
                if exists:
                    st.error("⚠️ Cette règle existe déjà")
                else:
                    st.session_state.rules.append({
                        'keyword': new_keyword,
                        'category': new_category
                    })
                    save_rules()
                    recategorize_all()
                    st.success(f"✅ Règle ajoutée : '{new_keyword}' → '{new_category}'")
                    st.rerun()
            else:
                st.error("⚠️ Veuillez remplir tous les champs")
    
    st.markdown("---")
    
    # Liste des règles
    st.markdown(f"### 📋 Règles actives ({len(st.session_state.rules)})")
    
    if st.session_state.rules:
        # Grouper par catégorie
        rules_by_category = {}
        for rule in st.session_state.rules:
            cat = rule['category']
            if cat not in rules_by_category:
                rules_by_category[cat] = []
            rules_by_category[cat].append(rule['keyword'])
        
        # Afficher par catégorie
        for category, keywords in sorted(rules_by_category.items()):
            with st.expander(f"📁 {category} ({len(keywords)} règles)"):
                for idx, rule in enumerate(st.session_state.rules):
                    if rule['category'] == category:
                        col1, col2, col3 = st.columns([2, 2, 1])
                        
                        rule_idx = st.session_state.rules.index(rule)
                        
                        with col1:
                            st.text_input(
                                f"kw_{rule_idx}",
                                value=rule['keyword'],
                                disabled=True,
                                label_visibility="collapsed"
                            )
                        
                        with col2:
                            st.text_input(
                                f"cat_{rule_idx}",
                                value=rule['category'],
                                disabled=True,
                                label_visibility="collapsed"
                            )
                        
                        with col3:
                            if st.button("🗑️", key=f"del_{rule_idx}", use_container_width=True):
                                st.session_state.rules.pop(rule_idx)
                                save_rules()
                                recategorize_all()
                                st.rerun()
        
        # Actions globales
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Recatégoriser toutes les transactions", use_container_width=True):
                recategorize_all()
                st.success("✅ Toutes les transactions ont été recatégorisées")
        
        with col2:
            if st.button("🗑️ Supprimer toutes les règles", type="secondary", use_container_width=True):
                if st.checkbox("⚠️ Confirmer la suppression"):
                    st.session_state.rules = []
                    save_rules()
                    recategorize_all()
                    st.success("✅ Toutes les règles ont été supprimées")
                    st.rerun()
    else:
        st.markdown("""
        <div class="warning-box">
            ⚠️ Aucune règle configurée. Ajoutez des règles pour automatiser la catégorisation !
        </div>
        """, unsafe_allow_html=True)
        
        # Suggestions de règles
        st.markdown("### 💡 Suggestions de règles courantes")
        suggestions = [
            ("colruyt", "Alimentation"),
            ("carrefour", "Alimentation"),
            ("lidl", "Alimentation"),
            ("shell", "Transport"),
            ("total", "Transport"),
            ("netflix", "Loisirs"),
            ("spotify", "Loisirs"),
            ("edf", "Logement"),
            ("eau", "Logement"),
        ]
        
        cols = st.columns(3)
        for idx, (keyword, category) in enumerate(suggestions):
            with cols[idx % 3]:
                if st.button(f"➕ {keyword} → {category}", key=f"sug_{idx}", use_container_width=True):
                    st.session_state.rules.append({'keyword': keyword, 'category': category})
                    save_rules()
                    recategorize_all()
                    st.rerun()

# ========================================
# PAGE: TRANSACTIONS
# ========================================
elif page == "📋 Transactions":
    st.header("📋 Liste des transactions")
    
    if st.session_state.all_transactions.empty:
        st.warning("⚠️ Aucune transaction chargée.")
    else:
        df = st.session_state.all_transactions.copy()
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            months = sorted(df['dateOp'].str[:7].unique(), reverse=True)
            selected_month_filter = st.selectbox(
                "📅 Mois",
                ["Tous"] + list(months),
                format_func=lambda x: x if x == "Tous" else datetime.strptime(x, "%Y-%m").strftime("%B %Y")
            )
        
        with col2:
            categories = ["Toutes"] + sorted(df['autoCategory'].unique().tolist())
            selected_category = st.selectbox("🏷️ Catégorie", categories)
        
        with col3:
            type_filter = st.selectbox("💰 Type", ["Tous", "Dépenses", "Revenus", "Mouvements internes"])
        
        # Appliquer les filtres
        filtered_df = df.copy()
        
        if selected_month_filter != "Tous":
            filtered_df = filtered_df[filtered_df['dateOp'].str.startswith(selected_month_filter)]
        
        if selected_category != "Toutes":
            filtered_df = filtered_df[filtered_df['autoCategory'] == selected_category]
        
        if type_filter == "Dépenses":
            filtered_df = filtered_df[filtered_df['amount'] < 0]
        elif type_filter == "Revenus":
            filtered_df = filtered_df[filtered_df['amount'] > 0]
        elif type_filter == "Mouvements internes":
            filtered_df = filtered_df[filtered_df['autoCategory'] == '💰 Mouvement interne']
        
        # Affichage
        st.markdown(f"### 📊 {len(filtered_df)} transactions")
        
        if not filtered_df.empty:
            # Statistiques rapides
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
            st.info("Aucune transaction ne correspond aux filtres sélectionnés")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; padding: 20px;'>
    💰 <strong>Gestionnaire de Dépenses Boursobank</strong><br>
    Vos données sont stockées localement et ne sont jamais partagées<br>
    Version 1.0 | Créé avec ❤️ et Streamlit
</div>
""", unsafe_allow_html=True)
