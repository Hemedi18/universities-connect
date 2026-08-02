from django.core.management.base import BaseCommand
from business.models import Region, District


class Command(BaseCommand):
    help = "Populates Tanzania Regions and Districts"

    def handle(self, *args, **kwargs):
        locations = {
            "Arusha": [
                "Arusha City",
                "Arusha District",
                "Karatu",
                "Longido",
                "Meru",
                "Monduli",
                "Ngorongoro",
            ],
            "Dar es Salaam": ["Ilala", "Kinondoni", "Temeke", "Kigamboni", "Ubungo"],
            "Dodoma": [
                "Bahi",
                "Chamwino",
                "Chemba",
                "Dodoma City",
                "Kondoa",
                "Kongwa",
                "Mpwapwa",
            ],
            "Geita": ["Bukombe", "Chato", "Geita", "Mbogwe", "Nyang'hwale"],
            "Iringa": ["Iringa", "Kilolo", "Mufindi"],
            "Kagera": [
                "Biharamulo",
                "Bukoba",
                "Karagwe",
                "Kyerwa",
                "Missenyi",
                "Muleba",
                "Ngara",
            ],
            "Katavi": ["Mlele", "Mpanda", "Tanganyika"],
            "Kigoma": ["Buhigwe", "Kakonko", "Kasulu", "Kibondo", "Kigoma", "Uvinza"],
            "Kilimanjaro": ["Hai", "Moshi", "Mwanga", "Rombo", "Same", "Siha"],
            "Lindi": ["Kilwa", "Lindi", "Liwale", "Nachingwea", "Ruangwa"],
            "Manyara": ["Babati", "Hanang", "Kiteto", "Mbulu", "Simanjiro"],
            "Mara": ["Bunda", "Butiama", "Musoma", "Rorya", "Serengeti", "Tarime"],
            "Mbeya": ["Busokelo", "Chunya", "Kyela", "Mbarali", "Mbeya", "Rungwe"],
            "Morogoro": [
                "Gairo",
                "Kilombero",
                "Kilosa",
                "Morogoro",
                "Mvomero",
                "Ulanga",
                "Malinyi",
            ],
            "Mtwara": ["Masasi", "Mtwara", "Nanyumbu", "Newala", "Tandahimba"],
            "Mwanza": [
                "Ilemela",
                "Kwimba",
                "Magu",
                "Misungwi",
                "Mwanza",
                "Sengerema",
                "Ukerewe",
            ],
            "Njombe": ["Ludewa", "Makete", "Njombe", "Wanging'ombe"],
            "Pemba North": ["Micheweni", "Wete"],
            "Pemba South": ["Chake Chake", "Mkoani"],
            "Pwani": [
                "Bagamoyo",
                "Kibaha",
                "Kisarawe",
                "Mafia",
                "Mkuranga",
                "Rufiji",
                "Kibiti",
            ],
            "Rukwa": ["Kalambo", "Nkasi", "Sumbawanga"],
            "Ruvuma": ["Mbinga", "Namtumbo", "Nyasa", "Songea", "Tunduru"],
            "Shinyanga": ["Kahama", "Kishapu", "Shinyanga"],
            "Simiyu": ["Bariadi", "Busega", "Itilima", "Maswa", "Meatu"],
            "Singida": ["Iramba", "Ikungi", "Manyoni", "Mkalama", "Singida"],
            "Songwe": ["Ileje", "Mbozi", "Momba", "Songwe"],
            "Tabora": [
                "Igunga",
                "Kaliua",
                "Nzega",
                "Sikonge",
                "Tabora",
                "Urambo",
                "Uyui",
            ],
            "Tanga": [
                "Handeni",
                "Kilindi",
                "Korogwe",
                "Lushoto",
                "Muheza",
                "Mkinga",
                "Pangani",
                "Tanga",
            ],
            "Zanzibar North": ["Kaskazini A", "Kaskazini B"],
            "Zanzibar South": ["Kati", "Kusini"],
            "Zanzibar Urban/West": ["Magharibi", "Mjini"],
        }

        for region_name, districts in locations.items():
            region, created = Region.objects.get_or_create(name=region_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created region: {region_name}"))

            for district_name in districts:
                district, d_created = District.objects.get_or_create(
                    region=region, name=district_name
                )
                if d_created:
                    self.stdout.write(
                        self.style.SUCCESS(f"  - Created district: {district_name}")
                    )

        self.stdout.write(
            self.style.SUCCESS("Successfully populated regions and districts")
        )
