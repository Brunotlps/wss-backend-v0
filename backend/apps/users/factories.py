"""Factory Boy factories for the users app."""

import factory
from factory.django import DjangoModelFactory

from .models import Profile, SocialAccount, User


class UserFactory(DjangoModelFactory):
    """Factory for regular student User."""

    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@test.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_instructor = False
    is_staff = False

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Hash and set password after user creation."""
        if create:
            obj.set_password(extracted or "testpass123!")
            obj.save()


class InstructorFactory(UserFactory):
    """Factory for instructor User."""

    is_instructor = True
    username = factory.Sequence(lambda n: f"instructor{n}")
    email = factory.Sequence(lambda n: f"instructor{n}@test.com")


class ProfileFactory(DjangoModelFactory):
    """Factory for user Profile (normally auto-created via signal)."""

    class Meta:
        model = Profile
        django_get_or_create = ("user",)

    user = factory.SubFactory(UserFactory)
    bio = factory.Faker("paragraph", nb_sentences=2)


class SocialAccountFactory(DjangoModelFactory):
    """Factory for SocialAccount (Google OAuth link)."""

    class Meta:
        model = SocialAccount

    user = factory.SubFactory(UserFactory)
    provider = SocialAccount.Provider.GOOGLE
    uid = factory.Sequence(lambda n: f"google-sub-{n:06d}")
    extra_data = factory.LazyAttribute(
        lambda o: {
            "email": o.user.email,
            "name": o.user.get_full_name(),
            "picture": "",
            "email_verified": True,
        }
    )
