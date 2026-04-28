import {
  trigger,
  transition,
  style,
  query,
  animate,
  group,
  stagger,
  animateChild,
} from '@angular/animations';

export const routeAnimations = trigger('routeAnimation', [
  transition('* <=> *', [
    query(':enter', [style({ opacity: 0, transform: 'translateY(16px)' })], {
      optional: true,
    }),
    group([
      query(
        ':leave',
        [animate('200ms ease-out', style({ opacity: 0, transform: 'translateY(-8px)' }))],
        { optional: true }
      ),
      query(
        ':enter',
        [animate('350ms 100ms ease-out', style({ opacity: 1, transform: 'translateY(0)' }))],
        { optional: true }
      ),
    ]),
    query(':enter', animateChild(), { optional: true }),
  ]),
]);

export const listStagger = trigger('listStagger', [
  transition('* => *', [
    query(
      ':enter',
      [
        style({ opacity: 0, transform: 'translateY(20px)' }),
        stagger(60, [
          animate('400ms ease-out', style({ opacity: 1, transform: 'translateY(0)' })),
        ]),
      ],
      { optional: true }
    ),
  ]),
]);
