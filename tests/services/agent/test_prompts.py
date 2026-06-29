from app.services.agent.prompts import SYSTEM_PROMPT_DEFAULT


def test_real_estate_prompt_is_loaded_and_has_no_minas_brisa_branding() -> None:
    assert "portugues do Brasil" in SYSTEM_PROMPT_DEFAULT
    assert "get_all_building" in SYSTEM_PROMPT_DEFAULT
    assert "search_building_information" in SYSTEM_PROMPT_DEFAULT
    assert '"response"' in SYSTEM_PROMPT_DEFAULT
    assert "lead_quality" in SYSTEM_PROMPT_DEFAULT
    assert "conversation_concluded" in SYSTEM_PROMPT_DEFAULT
    assert "demanda fora de escopo" in SYSTEM_PROMPT_DEFAULT
    assert "agendamento/handoff" in SYSTEM_PROMPT_DEFAULT
    assert "transfer_human representa" in SYSTEM_PROMPT_DEFAULT
    assert "contato inicial -> informacao -> nutricao/qualificacao" in SYSTEM_PROMPT_DEFAULT
    assert "cozinha, banheiro, garagem, jardim ou piscina" in SYSTEM_PROMPT_DEFAULT
    assert "sem pedir confirmacao desnecessaria" in SYSTEM_PROMPT_DEFAULT
    assert "Nao transforme inventario de midia em lista tecnica" in SYSTEM_PROMPT_DEFAULT
    assert "nao souber exatamente o que quer" in SYSTEM_PROMPT_DEFAULT
    assert "codigos de erro" in SYSTEM_PROMPT_DEFAULT
    assert "Minas Brisa" not in SYSTEM_PROMPT_DEFAULT
    assert "Bri" not in SYSTEM_PROMPT_DEFAULT
