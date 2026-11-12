-- ============================================================================
-- RankEngine - Script 03: Stored Procedures, Triggers e Histórico de Rodadas
-- ============================================================================

USE rank_engine;

-- ----------------------------------------------------------------------------
-- 1. TABELA DE HISTÓRICO DE EVOLUÇÃO POR RODADA
-- Alimentada automaticamente via Trigger quando partidas são finalizadas
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historico_evolucao (
    id INT AUTO_INCREMENT PRIMARY KEY,
    torneio_id INT NOT NULL,
    rodada INT NOT NULL,
    participante_id INT NOT NULL,
    posicao INT NOT NULL,
    pontos_acumulados DECIMAL(6,2) NOT NULL,
    saldo_acumulado INT NOT NULL,
    registrado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_hist_torneio FOREIGN KEY (torneio_id) REFERENCES torneios(id) ON DELETE CASCADE,
    CONSTRAINT fk_hist_participante FOREIGN KEY (participante_id) REFERENCES participantes(id) ON DELETE CASCADE,
    CONSTRAINT uq_hist_rodada UNIQUE (torneio_id, rodada, participante_id)
) ENGINE=InnoDB;

-- ----------------------------------------------------------------------------
-- 2. STORED PROCEDURE: Registrar ou Editar Placar de Confronto Direto
-- Busca as regras do torneio e calcula automaticamente vitória/empate/derrota
-- ----------------------------------------------------------------------------
DROP PROCEDURE IF EXISTS sp_registrar_confronto;

DELIMITER $$

CREATE PROCEDURE sp_registrar_confronto(
    IN p_partida_id INT,
    IN p_mandante_id INT,
    IN p_visitante_id INT,
    IN p_placar_mandante INT,
    IN p_placar_visitante INT
)
BEGIN
    DECLARE v_torneio_id INT;
    DECLARE v_pts_vit DECIMAL(5,2);
    DECLARE v_pts_emp DECIMAL(5,2);
    DECLARE v_pts_der DECIMAL(5,2);
    
    DECLARE v_pts_mandante DECIMAL(6,2);
    DECLARE v_pts_visitante DECIMAL(6,2);
    DECLARE v_res_mandante VARCHAR(20);
    DECLARE v_res_visitante VARCHAR(20);

    -- Handler para desfazer tudo caso ocorra erro no meio da transação
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    -- Busca o torneio e suas regras de pontuação
    SELECT t.id, t.pontos_vitoria, t.pontos_empate, t.pontos_derrota
      INTO v_torneio_id, v_pts_vit, v_pts_emp, v_pts_der
      FROM partidas pt
      INNER JOIN torneios t ON pt.torneio_id = t.id
     WHERE pt.id = p_partida_id;

    -- Define resultado e pontuação conforme o placar
    IF p_placar_mandante > p_placar_visitante THEN
        SET v_res_mandante = 'vitoria';
        SET v_res_visitante = 'derrota';
        SET v_pts_mandante = v_pts_vit;
        SET v_pts_visitante = v_pts_der;
    ELSEIF p_placar_mandante < p_placar_visitante THEN
        SET v_res_mandante = 'derrota';
        SET v_res_visitante = 'vitoria';
        SET v_pts_mandante = v_pts_der;
        SET v_pts_visitante = v_pts_vit;
    ELSE
        SET v_res_mandante = 'empate';
        SET v_res_visitante = 'empate';
        SET v_pts_mandante = v_pts_emp;
        SET v_pts_visitante = v_pts_emp;
    END IF;

    -- Insere ou atualiza o resultado do Mandante
    INSERT INTO resultados_partida (partida_id, participante_id, papel, pro, contra, pontos_obtidos, resultado)
    VALUES (p_partida_id, p_mandante_id, 'mandante', p_placar_mandante, p_placar_visitante, v_pts_mandante, v_res_mandante)
    ON DUPLICATE KEY UPDATE
        pro = VALUES(pro),
        contra = VALUES(contra),
        pontos_obtidos = VALUES(pontos_obtidos),
        resultado = VALUES(resultado);

    -- Insere ou atualiza o resultado do Visitante
    INSERT INTO resultados_partida (partida_id, participante_id, papel, pro, contra, pontos_obtidos, resultado)
    VALUES (p_partida_id, p_visitante_id, 'visitante', p_placar_visitante, p_placar_mandante, v_pts_visitante, v_res_visitante)
    ON DUPLICATE KEY UPDATE
        pro = VALUES(pro),
        contra = VALUES(contra),
        pontos_obtidos = VALUES(pontos_obtidos),
        resultado = VALUES(resultado);

    -- Marca a partida como finalizada (dispara a Trigger de histórico)
    UPDATE partidas
       SET status = 'finalizada'
     WHERE id = p_partida_id;

    COMMIT;
END$$

DELIMITER ;

-- ----------------------------------------------------------------------------
-- 3. TRIGGER: Atualiza o snapshot de evolução ao finalizar uma partida
-- ----------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_atualiza_historico_rodada;

DELIMITER $$

CREATE TRIGGER trg_atualiza_historico_rodada
AFTER UPDATE ON partidas
FOR EACH ROW
BEGIN
    IF NEW.status = 'finalizada' THEN
        INSERT INTO historico_evolucao (torneio_id, rodada, participante_id, posicao, pontos_acumulados, saldo_acumulado)
        SELECT 
            torneio_id,
            NEW.rodada,
            participante_id,
            posicao_ranking,
            pts,
            saldo
        FROM vw_classificacao_geral
        WHERE torneio_id = NEW.torneio_id
        ON DUPLICATE KEY UPDATE
            posicao = VALUES(posicao),
            pontos_acumulados = VALUES(pontos_acumulados),
            saldo_acumulado = VALUES(saldo_acumulado),
            registrado_em = CURRENT_TIMESTAMP;
    END IF;
END$$

DELIMITER ;