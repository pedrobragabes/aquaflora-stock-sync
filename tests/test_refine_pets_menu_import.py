from scripts.refine_pets_menu_import import ALLOWED_EXISTING_CATEGORIES, CATEGORY_BIRDS_RODENTS, classify_menu_category


def test_blocks_aquarismo_from_pets_menu():
    assert classify_menu_category("Carvao Ativado", "Aquarismo") is None
    assert classify_menu_category("Pedra Dolomita Nº0 1Kg - Aqua Pedras", "Aquarismo") is None
    assert classify_menu_category("Aquario Tv", "Aquarismo") is None
    assert classify_menu_category("La Acrilica Mt - Geral", "Aquarismo") is None
    assert classify_menu_category("Tronco Pequeno - Aqua Pedras", "Aquarismo") is None
    assert classify_menu_category("Planta Plast. Grande - Mr Pet", "Aquarismo") is None


def test_uses_only_existing_woocommerce_category_paths():
    assert "Pets > Pássaros & Roedores" not in ALLOWED_EXISTING_CATEGORIES
    assert CATEGORY_BIRDS_RODENTS == "Pets > Pássaros & Roedores > Gaiolas"
    assert all(category.startswith("Pets > ") for category in ALLOWED_EXISTING_CATEGORIES)


def test_maps_cat_litter_to_gatos_areias_higiene():
    assert (
        classify_menu_category("Areia Pipicat Classic 12Kg - Kelco", "Pet > Areias Tapetes & Banheiro")
        == "Pets > Gatos > Areias & Higiene"
    )
    assert (
        classify_menu_category("Bio Granulado Higienico 3Kg - New-Pellet", "Pet > Areias Tapetes & Banheiro")
        == "Pets > Gatos > Areias & Higiene"
    )


def test_moves_items_out_of_higiene_when_name_says_accessory_or_toy():
    assert (
        classify_menu_category("Comedouro Pet C/ Ventosa - Raimundo Pet", "Pet > Higiene & Banho")
        == "Pets > Cães > Acessórios Cães"
    )
    assert (
        classify_menu_category("Brinquedo Mordedor Puxador Bola C/Ventosa - Napi", "Pet > Higiene & Banho")
        == "Pets > Cães > Brinquedos Cães"
    )


def test_color_words_do_not_send_accessories_to_farmacia():
    assert (
        classify_menu_category("Peitoral Police Vermelho", "Pet > Acessorios > Coleiras Guias & Peitorais")
        == "Pets > Cães > Acessórios Cães"
    )
    assert (
        classify_menu_category("Comedouro Anti Formiga Gato Vermelho", "Pet > Acessorios > Comedouros & Bebedouros")
        == "Pets > Gatos > Acessórios & Brinquedos Gatos"
    )


def test_blocks_aquarium_terms_even_when_source_category_is_wrong():
    assert classify_menu_category("Filtro Canister Dophin", "Pet > Acessorios") is None


def test_maps_core_dog_and_cat_menu_categories():
    assert classify_menu_category("Sache Special Dog Carne 100G", "Pet > Racoes & Saches") == "Pets > Cães > Rações Cães"
    assert classify_menu_category("Sache Special Cat Frango 85G", "Pet > Racoes & Saches") == "Pets > Gatos > Rações Gatos"
    assert classify_menu_category("Petisco Bifinho Carne 400G", "Pet > Racoes & Saches") == "Pets > Cães > Petiscos Cães"


def test_maps_farmacia_menu_categories_and_blocks_agro_noise():
    assert (
        classify_menu_category("Bravecto Antipulgas Caes 10 A 20Kg", "Farmacia Pet")
        == "Pets > Farmácia Veterinária > Antipulgas & Vermífugos"
    )
    assert classify_menu_category("Hemolitan Pet 30Ml", "Farmacia Pet") == "Pets > Farmácia Veterinária > Suplementos"
    assert classify_menu_category("Glifosato 1L", "Farmacia Pet") is None
    assert classify_menu_category("Raticida Straik 25G - Dexter", "Farmacia Pet") is None
    assert classify_menu_category("Brinco Bezerro Bhl/Jur Médio Liso - Allflex", "Farmacia Pet") is None
