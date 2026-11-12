-- ============================================================================
-- RankEngine - Script 02: Views Analíticas e Ranking com Window Functions
-- ============================================================================

USE rank_engine;

-- Remove a view se já existir para permitir reexecução limpa
DROP VIEW IF EXISTS vw_classificacao_geral;

-- ----------------------------------------------------------------------------
-- VIEW: vw_classificacao_geral
-- Calcula estatísticas acumuladas e ordena posições via DENSE_RANK()
-- ----------------------------------------------------------------------------
CREATE VIEW vw_classificacao_geral AS
WITH estatisticas_participante AS (
    SELECT 
        t.id AS torneio_id,
        t.nome AS torneio_nome,
        t.modalidade,
        p.id AS participante_id,
        p.nome AS participante_nome,
        p.sigla,
        p.grupo,
        p.escudo_url,
        p.bandeira_url,
        p.posicao_manual,
        
        -- Soma total de pontos (COALESCE garante 0 caso ainda não tenha partidas)
        COALESCE(SUM(CASE WHEN pt.status = 'finalizada' THEN rp.pontos_obtidos ELSE 0 END), 0) AS pts,
        
        -- Partidas Jogadas (apenas partidas finalizadas)
        COUNT(CASE WHEN pt.status = 'finalizada' THEN rp.id END) AS pj,
        
        -- Vitórias, Empates e Derrotas
        COUNT(CASE WHEN pt.status = 'finalizada' AND rp.resultado = 'vitoria' THEN 1 END) AS vit,
        COUNT(CASE WHEN pt.status = 'finalizada' AND rp.resultado = 'empate' THEN 1 END) AS emp,
        COUNT(CASE WHEN pt.status = 'finalizada' AND rp.resultado = 'derrota' THEN 1 END) AS der,
        
        -- Pró, Contra e Saldo (gols, sets ou pontos na etapa)
        COALESCE(SUM(CASE WHEN pt.status = 'finalizada' THEN rp.pro ELSE 0 END), 0) AS pro,
        COALESCE(SUM(CASE WHEN pt.status = 'finalizada' THEN rp.contra ELSE 0 END), 0) AS contra,
        COALESCE(SUM(CASE WHEN pt.status = 'finalizada' THEN (rp.pro - rp.contra) ELSE 0 END), 0) AS saldo,
        
        -- Aproveitamento percentual baseado nos pontos máximos possíveis (pontos_vitoria * pj)
        CASE 
            WHEN COUNT(CASE WHEN pt.status = 'finalizada' THEN rp.id END) = 0 THEN 0.0
            ELSE ROUND(
                (COALESCE(SUM(CASE WHEN pt.status = 'finalizada' THEN rp.pontos_obtidos ELSE 0 END), 0) / 
                (COUNT(CASE WHEN pt.status = 'finalizada' THEN rp.id END) * t.pontos_vitoria)) * 100, 
            1)
        END AS aproveitamento
        
    FROM participantes p
    INNER JOIN torneios t ON p.torneio_id = t.id
    LEFT JOIN resultados_partida rp ON rp.participante_id = p.id
    LEFT JOIN partidas pt ON rp.partida_id = pt.id
    GROUP BY 
        t.id, t.nome, t.modalidade, t.pontos_vitoria,
        p.id, p.nome, p.sigla, p.grupo, p.escudo_url, p.bandeira_url, p.posicao_manual
)
SELECT 
    *,
    -- Window Function: calcula a posição no ranking particionada por torneio e grupo
    DENSE_RANK() OVER (
        PARTITION BY torneio_id, COALESCE(grupo, 'GERAL')
        ORDER BY 
            CASE WHEN posicao_manual IS NOT NULL THEN 0 ELSE 1 END,
            posicao_manual ASC,
            pts DESC,
            vit DESC,
            saldo DESC,
            pro DESC,
            participante_nome ASC
    ) AS posicao_ranking
FROM estatisticas_participante;